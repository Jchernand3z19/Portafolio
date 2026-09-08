import { requireProductionEnv } from '@/src/config/env';

interface MediaMetadata {
  id: string;
  url: string;
  mime_type?: string;
  file_size?: number;
  sha256?: string;
}

function graphUrl(version: string, path: string): string {
  return `https://graph.facebook.com/${version}/${path}`;
}

function bearerHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export async function downloadWhatsAppMedia(mediaId: string): Promise<{ bytes: Buffer; mimeType?: string; size?: number }> {
  const config = requireProductionEnv('WHATSAPP_ACCESS_TOKEN');
  const version = process.env.WHATSAPP_GRAPH_VERSION?.trim() || 'v26.0';
  const metadataResponse = await fetch(graphUrl(version, encodeURIComponent(mediaId)), {
    headers: bearerHeaders(config.WHATSAPP_ACCESS_TOKEN),
    cache: 'no-store',
  });
  if (!metadataResponse.ok) throw new Error(`whatsapp_media_metadata_failed:${metadataResponse.status}`);
  const metadata = await metadataResponse.json() as MediaMetadata;
  if (!metadata.url || metadata.id !== mediaId) throw new Error('whatsapp_media_metadata_invalid');

  const mediaResponse = await fetch(metadata.url, {
    headers: bearerHeaders(config.WHATSAPP_ACCESS_TOKEN),
    cache: 'no-store',
    redirect: 'follow',
  });
  if (!mediaResponse.ok) throw new Error(`whatsapp_media_download_failed:${mediaResponse.status}`);
  const bytes = Buffer.from(await mediaResponse.arrayBuffer());
  return {
    bytes,
    mimeType: mediaResponse.headers.get('content-type')?.split(';')[0] || metadata.mime_type,
    size: metadata.file_size,
  };
}

export async function sendWhatsAppText(phone: string, body: string): Promise<void> {
  const config = requireProductionEnv('WHATSAPP_ACCESS_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID');
  const version = process.env.WHATSAPP_GRAPH_VERSION?.trim() || 'v26.0';
  const response = await fetch(graphUrl(version, `${encodeURIComponent(config.WHATSAPP_PHONE_NUMBER_ID)}/messages`), {
    method: 'POST',
    headers: {
      ...bearerHeaders(config.WHATSAPP_ACCESS_TOKEN),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messaging_product: 'whatsapp',
      recipient_type: 'individual',
      to: phone,
      type: 'text',
      text: { preview_url: false, body },
    }),
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`whatsapp_send_failed:${response.status}`);
}
