export const PAYMENT_STATUSES = [
  'COMPROBANTE_RECIBIDO',
  'PROCESANDO',
  'EXTRAIDO',
  'SIN_IDENTIFICAR',
  'ESPERANDO_RESPUESTA',
  'PENDIENTE_VERIFICACION',
  'VERIFICADO',
  'DUPLICADO',
  'NO_ENCONTRADO',
  'EN_REVISION',
  'RECHAZADO',
] as const;

export type PaymentStatus = (typeof PAYMENT_STATUSES)[number];

export interface HomeRef {
  stage: number;
  block: number;
  house: number;
}

export interface HomeRecord extends HomeRef {
  id: string;
  responsible?: string;
  monthlyFee: number;
  active: boolean;
  startDate?: string;
  endDate?: string;
}

export interface ReceiptExtraction {
  bank: string;
  depositor?: string;
  transactionDate?: string;
  transactionTime?: string;
  amount?: number;
  detail?: string;
  reference?: string;
  beneficiary?: string;
  destinationAccountMasked?: string;
  home?: HomeRef;
  confidence: number;
  rawText?: string;
  warnings: string[];
}

export interface PaymentRecord {
  id: string;
  createdAt: string;
  updatedAt: string;
  sourceMessageId: string;
  /** WhatsApp sender. It is never housing identity. */
  phone: string;
  bank: string;
  depositor?: string;
  transactionDate?: string;
  transactionTime?: string;
  /** Amount shown by the bank receipt. */
  amount: number;
  detail?: string;
  reference?: string;
  beneficiary?: string;
  destinationAccountMasked?: string;
  stage?: number;
  block?: number;
  house?: number;
  /** Service month paid, YYYY-MM. */
  period: string;
  status: PaymentStatus;
  /** SHA-256 of the transient receipt bytes; the image itself is not retained. */
  fileHash: string;
  duplicateOf?: string;
  duplicateReason?: string;
  reviewReason?: string;
  verificationSource?: string;
  verifiedAt?: string;
  /** Stable identifier from an authorized bank-side movement source, when available. */
  bankMovementId?: string;
}

export interface PendingConversation {
  id: string;
  /** WhatsApp sender used only to correlate the requested E/B/C reply. */
  phone: string;
  paymentId: string;
  createdAt: string;
  expiresAt: string;
}

export interface ProcessedMessage {
  messageId: string;
  receivedAt: string;
  kind: 'image' | 'text' | 'document' | 'other';
  outcome: 'processed' | 'ignored' | 'rejected';
}

export interface DashboardBlockSummary {
  stage: number;
  block: number;
  totalHomes: number;
  paidHomes: number;
  pendingHomes: number;
  /** Bank-verified amount only. */
  collected: number;
  collectionRate: number;
}

export interface DashboardPaymentRow extends PaymentRecord {
  homeLabel: string;
  /** Expected fee from the housing master; not copied from the receipt. */
  monthlyFee?: number;
}

export interface DashboardSnapshot {
  period: string;
  totalHomes: number;
  /** Homes with at least one bank-verified payment for the service month. */
  paidHomes: number;
  pendingHomes: number;
  collectionRate: number;
  expectedAmount: number;
  receivedAmount: number;
  verifiedAmount: number;
  pendingAmount: number;
  unidentifiedAmount: number;
  blocks: DashboardBlockSummary[];
  payments: DashboardPaymentRow[];
  unidentified: DashboardPaymentRow[];
  duplicates: DashboardPaymentRow[];
  review: DashboardPaymentRow[];
}

export function homeKey(home: HomeRef): string {
  return `E${home.stage}-B${home.block}-C${home.house}`;
}
