import { apiFetch } from "./client";
import type { MasterReport, MasterReportDetail } from "./reports";

/** Who a master is addressed to, as far as the responsible body's record says. */
export type LetterRecipient = {
  name: string;
  /** null when the body's record has no address to write to */
  email: string | null;
  contact?: { url: string; description: string | null };
};

/**
 * The filing as a letter: who it goes to and what it says. Built here from the
 * master and the body it is assigned to, since the API does not compose one.
 */
export type ReportLetter = {
  /** null until an office or a service entity is made responsible */
  recipient: LetterRecipient | null;
  subject: string;
  body: string;
};

// the fields read off the catalogue records; both carry many more
type LocalGovernmentOffice = {
  id: number;
  local_government_name: string;
  office_name: string | null;
  email: string | null;
};

type ServiceEntity = {
  id: number;
  name: string;
  email: string | null;
  /** a form URL, or a tel: or mailto: URI */
  reporting_channel: string | null;
  reporting_channel_description?: string | null;
};

function office(
  id: number,
  signal?: AbortSignal,
): Promise<LocalGovernmentOffice> {
  return apiFetch(`/institution-contacts/${id}`, { signal });
}

function serviceEntity(
  id: number,
  signal?: AbortSignal,
): Promise<ServiceEntity> {
  return apiFetch(`/service-entities/${id}`, { signal });
}

// a dedicated reporting inbox is preferred to the general one
function entityEmail(entity: ServiceEntity): string | null {
  const channel = entity.reporting_channel?.trim() ?? "";
  if (/^mailto:/i.test(channel)) {
    const address = channel.slice("mailto:".length).split("?", 1)[0].trim();
    if (address) return address;
  }
  return entity.email?.trim() || null;
}

function entityRecipient(entity: ServiceEntity): LetterRecipient {
  const recipient: LetterRecipient = {
    name: entity.name,
    email: entityEmail(entity),
  };
  const channel = entity.reporting_channel?.trim();
  if (!recipient.email && channel && /^(https?:\/\/|tel:)/i.test(channel)) {
    recipient.contact = {
      url: channel,
      description: entity.reporting_channel_description ?? null,
    };
  }
  return recipient;
}

/** The body the master is assigned to, or null while it is not assigned. */
export async function letterRecipient(
  master: MasterReport,
  signal?: AbortSignal,
): Promise<LetterRecipient | null> {
  if (master.responsible_service_entity_id !== null) {
    const entity = await serviceEntity(
      master.responsible_service_entity_id,
      signal,
    );
    return entityRecipient(entity);
  }
  if (master.responsible_office_id !== null) {
    const record = await office(master.responsible_office_id, signal);
    return {
      name: record.office_name ?? record.local_government_name,
      email: record.email,
    };
  }
  return null;
}

/** The master as the letter its sheet shows. */
export async function letterFor(
  master: MasterReport,
  signal?: AbortSignal,
): Promise<ReportLetter> {
  return {
    recipient: await letterRecipient(master, signal),
    subject: master.title,
    body: master.description,
  };
}

export async function recommendedRecipient(
  master: MasterReportDetail,
  signal?: AbortSignal,
): Promise<LetterRecipient | null> {
  const form = new FormData();
  form.set(
    "payload",
    JSON.stringify({
      title: master.title,
      description: master.description,
      source_language: "pl",
      location: master.location,
    }),
  );
  const photo = master.photos[0];
  if (photo) {
    const image = await apiFetch<Blob>(photo.url, {
      responseType: "blob",
      signal,
    });
    form.set("image", image, photo.storage_key.split("/").pop());
  }
  const result = await apiFetch<{
    recommendation: { entity: ServiceEntity } | null;
  }>("/inference/service-entity/recommendation", {
    method: "POST",
    body: form,
    signal,
  });
  if (!result.recommendation) return null;
  const { entity } = result.recommendation;
  return entityRecipient(entity);
}

export function letterMailto(
  recipient: LetterRecipient,
  letter: ReportLetter,
): string {
  return `mailto:${recipient.email ?? ""}?subject=${encodeURIComponent(letter.subject)}&body=${encodeURIComponent(letter.body)}`;
}
