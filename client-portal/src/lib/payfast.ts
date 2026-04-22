import { createHash } from 'crypto';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const PAYFAST_SANDBOX_URL = 'https://sandbox.payfast.co.za/eng/process';
const PAYFAST_LIVE_URL = 'https://www.payfast.co.za/eng/process';
const PAYFAST_SANDBOX_VALIDATE_URL = 'https://sandbox.payfast.co.za/eng/query/validate';
const PAYFAST_LIVE_VALIDATE_URL = 'https://www.payfast.co.za/eng/query/validate';

const MERCHANT_ID = process.env.PAYFAST_MERCHANT_ID ?? '';
const MERCHANT_KEY = process.env.PAYFAST_MERCHANT_KEY ?? '';
const PASSPHRASE = process.env.PAYFAST_PASSPHRASE ?? '';
const IS_SANDBOX = process.env.PAYFAST_SANDBOX === 'true';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PayFastPaymentData {
  merchant_id: string;
  merchant_key: string;
  return_url: string;
  cancel_url: string;
  notify_url: string;
  name_first: string;
  name_last: string;
  email_address: string;
  m_payment_id: string;
  amount: string;
  item_name: string;
  item_description: string;
  subscription_type: '1';
  billing_date: string;
  recurring_amount: string;
  frequency: '3' | '6';
  cycles: '0';
  signature: string;
}

export interface PayFastITNData {
  pf_payment_id: string;
  payment_status: string;
  amount_gross: string;
  amount_fee: string;
  amount_net: string;
  m_payment_id: string;
  item_name: string;
  item_description?: string;
  token?: string;
  custom_str1?: string;
  custom_str2?: string;
  custom_str3?: string;
  custom_str4?: string;
  custom_str5?: string;
  custom_int1?: string;
  custom_int2?: string;
  custom_int3?: string;
  custom_int4?: string;
  custom_int5?: string;
  name_first?: string;
  name_last?: string;
  email_address?: string;
  merchant_id?: string;
  signature?: string;
  billing_date?: string;
  [key: string]: string | undefined;
}

export interface GeneratePaymentParams {
  clientId: string;
  clientEmail: string;
  clientName: string;
  planName: string;
  /** Amount in cents (e.g. 599900 = R5,999.00) */
  amount: number;
  billingInterval: 'monthly' | 'yearly';
  returnUrl: string;
  cancelUrl: string;
  notifyUrl: string;
}

// ---------------------------------------------------------------------------
// Signature generation
// ---------------------------------------------------------------------------

/**
 * Generates an MD5 signature from a key-value data object.
 *
 * 1. Sorts keys alphabetically.
 * 2. Builds a URL-encoded query string.
 * 3. Appends the passphrase (if provided).
 * 4. Returns the MD5 hex digest.
 */
export function generateSignature(
  data: Record<string, string>,
  passphrase?: string,
): string {
  const sortedKeys = Object.keys(data).sort();

  const queryString = sortedKeys
    .filter((key) => data[key] !== undefined && data[key] !== '')
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(data[key]).replace(/%20/g, '+')}`)
    .join('&');

  const toHash = passphrase
    ? `${queryString}&passphrase=${encodeURIComponent(passphrase).replace(/%20/g, '+')}`
    : queryString;

  return createHash('md5').update(toHash).digest('hex');
}

// ---------------------------------------------------------------------------
// Payment data builder
// ---------------------------------------------------------------------------

/**
 * Builds the full set of PayFast form fields for a subscription payment.
 */
export function generatePaymentData(params: GeneratePaymentParams): PayFastPaymentData {
  const {
    clientId,
    clientEmail,
    clientName,
    planName,
    amount,
    billingInterval,
    returnUrl,
    cancelUrl,
    notifyUrl,
  } = params;

  // Split name into first / last
  const nameParts = clientName.trim().split(/\s+/);
  const nameFirst = nameParts[0] ?? '';
  const nameLast = nameParts.length > 1 ? nameParts.slice(1).join(' ') : '';

  // Amount: convert cents to rands with 2 decimal places
  const amountRands = (amount / 100).toFixed(2);

  // Unique payment reference
  const mPaymentId = `AVM-${clientId}-${Date.now()}`;

  // Billing date: 14-day free trial from today
  const trialEnd = new Date();
  trialEnd.setDate(trialEnd.getDate() + 14);
  const billingDate = trialEnd.toISOString().slice(0, 10); // YYYY-MM-DD

  // Frequency: 3 = monthly, 6 = annual
  const frequency: '3' | '6' = billingInterval === 'monthly' ? '3' : '6';

  const itemName = `AnyVision ${planName} - ${billingInterval === 'monthly' ? 'Monthly' : 'Yearly'}`;

  // Build data object (without signature)
  const data: Record<string, string> = {
    merchant_id: MERCHANT_ID,
    merchant_key: MERCHANT_KEY,
    return_url: returnUrl,
    cancel_url: cancelUrl,
    notify_url: notifyUrl,
    name_first: nameFirst,
    name_last: nameLast,
    email_address: clientEmail,
    m_payment_id: mPaymentId,
    amount: amountRands,
    item_name: itemName,
    item_description: `${planName} subscription for AnyVision Media client portal`,
    subscription_type: '1',
    billing_date: billingDate,
    recurring_amount: amountRands,
    frequency,
    cycles: '0',
  };

  const signature = generateSignature(data, PASSPHRASE || undefined);

  return {
    ...data,
    signature,
  } as PayFastPaymentData;
}

// ---------------------------------------------------------------------------
// ITN validation
// ---------------------------------------------------------------------------

/**
 * Validates an Instant Transaction Notification by re-computing the signature.
 * Returns true when the computed signature matches the one PayFast sent.
 */
export function validateITN(data: Record<string, string>): boolean {
  const { signature, ...rest } = data;
  if (!signature) return false;

  const computed = generateSignature(rest, PASSPHRASE || undefined);
  return computed === signature;
}

// ---------------------------------------------------------------------------
// Server-side confirmation with PayFast
// ---------------------------------------------------------------------------

/**
 * Confirms a payment notification directly with PayFast's servers.
 * `pfParamString` is the full URL-encoded body that was received in the ITN POST.
 */
export async function confirmWithPayFast(pfParamString: string): Promise<boolean> {
  const validateUrl = IS_SANDBOX
    ? PAYFAST_SANDBOX_VALIDATE_URL
    : PAYFAST_LIVE_VALIDATE_URL;

  try {
    const response = await fetch(validateUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: pfParamString,
    });

    const text = await response.text();
    return text.trim().toUpperCase() === 'VALID';
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Converts a cent value to a formatted ZAR string.
 *
 * @example formatZAR(599900)   -> "R5,999.00"
 * @example formatZAR(1499900)  -> "R14,999.00"
 */
export function formatZAR(cents: number): string {
  const rands = cents / 100;
  const formatted = rands.toLocaleString('en-ZA', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `R${formatted}`;
}

/**
 * Returns the PayFast process URL (sandbox or live) based on environment config.
 */
export function getPayFastUrl(): string {
  return IS_SANDBOX ? PAYFAST_SANDBOX_URL : PAYFAST_LIVE_URL;
}
