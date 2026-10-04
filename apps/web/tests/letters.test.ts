import { beforeEach, describe, expect, mock, test } from "bun:test";
import type { MasterReportDetail } from "../src/api/reports";

const apiFetch = mock();
mock.module("../src/api/client", () => ({ apiFetch }));
const { letterFor, letterMailto, recommendedRecipient } =
  await import("../src/api/letters");

const master: MasterReportDetail = {
  id: "report-1",
  report_category_id: 1,
  status_id: 1,
  responsible_office_id: null,
  responsible_service_entity_id: null,
  title: "Dziura & chodnik?",
  description: "Uszkodzony chodnik.\nProszę o naprawę.",
  location: { longitude: 19.938, latitude: 50.061 },
  response: null,
  report_count: 1,
  created_at: "2026-10-04T10:00:00Z",
  edited_at: "2026-10-04T10:00:00Z",
  photos: [],
};
const entity = {
  id: 7,
  name: "Zarząd dróg",
  email: "office@example.org",
  reporting_channel: "mailto:reports@example.org?subject=Existing",
};

beforeEach(() => apiFetch.mockReset());

describe("marker letters", () => {
  test("keeps the report text and assigned recipient without requesting inference", async () => {
    apiFetch.mockResolvedValueOnce(entity);
    const letter = await letterFor({
      ...master,
      responsible_service_entity_id: entity.id,
    });
    expect(letter).toEqual({
      recipient: { name: entity.name, email: "reports@example.org" },
      subject: master.title,
      body: master.description,
    });
    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(apiFetch.mock.calls[0][0]).toBe("/service-entities/7");
  });

  test("requests a recommendation with the report location and first photo", async () => {
    const image = new Blob(["photo"], { type: "image/png" });
    const photo = {
      id: "photo-1",
      report_id: master.id,
      storage_key: "reports/report-1/photo-1.png",
      url: "/photos/photo-1/file",
      created_at: master.created_at,
    };
    const signal = new AbortController().signal;
    apiFetch
      .mockResolvedValueOnce(image)
      .mockResolvedValueOnce({ recommendation: { entity } });
    expect(
      await recommendedRecipient({ ...master, photos: [photo] }, signal),
    ).toEqual({ name: entity.name, email: "reports@example.org" });
    expect(apiFetch.mock.calls[0]).toEqual([
      photo.url,
      { responseType: "blob", signal },
    ]);
    const [path, options] = apiFetch.mock.calls[1];
    expect(path).toBe("/inference/service-entity/recommendation");
    expect(options.method).toBe("POST");
    expect(options.signal).toBe(signal);
    expect(JSON.parse(options.body.get("payload"))).toEqual({
      title: master.title,
      description: master.description,
      source_language: "pl",
      location: master.location,
    });
    expect(await options.body.get("image").text()).toBe("photo");
  });

  test("supports text-only reports and falls back to the institution email", async () => {
    apiFetch.mockResolvedValueOnce({
      recommendation: {
        entity: { ...entity, reporting_channel: "https://example.org/form" },
      },
    });
    expect(await recommendedRecipient(master)).toEqual({
      name: entity.name,
      email: entity.email,
    });
    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(apiFetch.mock.calls[0][1].body.has("image")).toBe(false);
  });

  test("preserves an empty recommendation and missing email", async () => {
    apiFetch.mockResolvedValueOnce({ recommendation: null });
    expect(await recommendedRecipient(master)).toBeNull();
    apiFetch.mockResolvedValueOnce({
      recommendation: {
        entity: { ...entity, reporting_channel: null, email: null },
      },
    });
    expect(await recommendedRecipient(master)).toEqual({
      name: entity.name,
      email: null,
    });
  });

  test("propagates unavailable recommendations for the dialog retry state", async () => {
    apiFetch.mockRejectedValueOnce(new Error("Model inference failed"));
    await expect(recommendedRecipient(master)).rejects.toThrow(
      "Model inference failed",
    );
  });

  test.each(["https://example.org/contact", "tel:+48123456789"])(
    "retains the published contact channel when there is no mailbox: %s",
    async (channel) => {
      apiFetch.mockResolvedValueOnce({
        recommendation: {
          entity: {
            ...entity,
            email: null,
            reporting_channel: channel,
            reporting_channel_description: "Public contact",
          },
        },
      });
      expect(await recommendedRecipient(master)).toEqual({
        name: entity.name,
        email: null,
        contact: { url: channel, description: "Public contact" },
      });
    },
  );

  test("an empty mailto does not hide the general mailbox", async () => {
    apiFetch.mockResolvedValueOnce({
      recommendation: {
        entity: { ...entity, reporting_channel: "mailto:?subject=Report" },
      },
    });
    expect(await recommendedRecipient(master)).toEqual({
      name: entity.name,
      email: entity.email,
    });
  });

  test("prefills the email subject and unchanged body without breaking on punctuation", async () => {
    const letter = await letterFor(master);
    const href = new URL(
      letterMailto({ name: entity.name, email: entity.email }, letter),
    );
    expect(href.pathname).toBe(entity.email);
    expect(href.searchParams.get("subject")).toBe(master.title);
    expect(href.searchParams.get("body")).toBe(master.description);
  });
});
