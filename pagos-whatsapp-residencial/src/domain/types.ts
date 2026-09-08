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
  block: number;
  house: number;
}

export interface HomeRecord extends HomeRef {
  id: string;
  phone?: string;
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
  phone: string;
  mediaId?: string;
  bank: string;
  depositor?: string;
  transactionDate?: string;
  transactionTime?: string;
  amount: number;
  detail?: string;
  reference?: string;
  beneficiary?: string;
  destinationAccountMasked?: string;
  block?: number;
  house?: number;
  period: string;
  status: PaymentStatus;
  fileHash: string;
  duplicateOf?: string;
  reviewReason?: string;
  verificationSource?: string;
  verifiedAt?: string;
}

export interface PendingConversation {
  id: string;
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
  block: number;
  totalHomes: number;
  paidHomes: number;
  pendingHomes: number;
  collected: number;
  collectionRate: number;
}

export interface DashboardPaymentRow extends PaymentRecord {
  homeLabel: string;
}

export interface DashboardSnapshot {
  period: string;
  totalHomes: number;
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
  return `B${home.block}-C${home.house}`;
}
