import { Readable } from 'node:stream';
import { google } from 'googleapis';
import { requireProductionEnv } from '@/src/config/env';
import type { AllowedReceiptMime } from '@/src/security/files';

export interface ReceiptArchive {
  save(bytes: Buffer, mimeType: AllowedReceiptMime, sha256: string): Promise<string>;
  read(fileId: string): Promise<{ bytes: Buffer; mimeType: string }>;
}

export class GoogleDriveReceiptArchive implements ReceiptArchive {
  private readonly folderId: string;
  private readonly drive;

  constructor() {
    const config = requireProductionEnv('GOOGLE_CLIENT_EMAIL', 'GOOGLE_PRIVATE_KEY', 'GOOGLE_RECEIPT_FOLDER_ID');
    const auth = new google.auth.JWT({
      email: config.GOOGLE_CLIENT_EMAIL,
      key: config.GOOGLE_PRIVATE_KEY.replace(/\\n/g, '\n'),
      scopes: ['https://www.googleapis.com/auth/drive.file'],
    });
    this.folderId = config.GOOGLE_RECEIPT_FOLDER_ID;
    this.drive = google.drive({ version: 'v3', auth });
  }

  async save(bytes: Buffer, mimeType: AllowedReceiptMime, sha256: string): Promise<string> {
    const extension = mimeType === 'image/png' ? 'png' : 'jpg';
    const response = await this.drive.files.create({
      requestBody: {
        name: `receipt-${sha256.slice(0, 24)}.${extension}`,
        parents: [this.folderId],
        appProperties: { receipt_sha256: sha256 },
      },
      media: { mimeType, body: Readable.from(bytes) },
      fields: 'id',
      supportsAllDrives: true,
    });
    if (!response.data.id) throw new Error('receipt_archive_create_failed');
    return response.data.id;
  }

  async read(fileId: string): Promise<{ bytes: Buffer; mimeType: string }> {
    const metadata = await this.drive.files.get({ fileId, fields: 'id,mimeType', supportsAllDrives: true });
    const mimeType = metadata.data.mimeType;
    if (mimeType !== 'image/jpeg' && mimeType !== 'image/png') throw new Error('receipt_archive_mime_invalid');
    const response = await this.drive.files.get(
      { fileId, alt: 'media', supportsAllDrives: true },
      { responseType: 'arraybuffer' },
    );
    return { bytes: Buffer.from(response.data as ArrayBuffer), mimeType };
  }
}
