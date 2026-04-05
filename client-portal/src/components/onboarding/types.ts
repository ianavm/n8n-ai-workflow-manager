export interface StepData {
  business_profile?: {
    industry: string;
    company_size: string;
    primary_need: string;
    phone_number?: string;
    company_name?: string;
  };
  connect_tools?: {
    selected_tools: string[];
  };
  choose_automation?: {
    selected_template: string | null;
  };
  preview?: {
    viewed: boolean;
  };
}

export interface OnboardingProgress {
  id: string;
  client_id: string;
  current_step: number;
  step_data: StepData;
  completed_steps: number[];
  skipped_steps: number[];
  started_at: string;
  completed_at: string | null;
  updated_at: string;
}

export interface StepProps {
  stepData: StepData;
  onUpdate: (data: Partial<StepData>) => void;
  onNext: () => void;
  onSkip: () => void;
  onBack: () => void;
  isFirst: boolean;
  isLast: boolean;
  loading: boolean;
}

export const INDUSTRIES = [
  { value: "retail", label: "Retail & E-commerce" },
  { value: "real_estate", label: "Real Estate" },
  { value: "professional_services", label: "Professional Services" },
  { value: "healthcare", label: "Healthcare" },
  { value: "hospitality", label: "Hospitality & Tourism" },
  { value: "automotive", label: "Automotive" },
  { value: "financial_services", label: "Financial Services" },
  { value: "construction", label: "Construction & Property" },
  { value: "education", label: "Education & Training" },
  { value: "other", label: "Other" },
] as const;

export const COMPANY_SIZES = [
  { value: "solo", label: "Just me" },
  { value: "2-10", label: "2-10 employees" },
  { value: "11-50", label: "11-50 employees" },
  { value: "51-200", label: "51-200 employees" },
  { value: "200+", label: "200+ employees" },
] as const;

export const PRIMARY_NEEDS = [
  { value: "marketing", label: "Marketing & Lead Generation", description: "Social media, ads, content, SEO" },
  { value: "accounting", label: "Accounting & Finance", description: "Invoicing, collections, reconciliation" },
  { value: "advisory", label: "Business Advisory", description: "Client management, compliance, reporting" },
  { value: "all", label: "All-in-one Automation", description: "Everything above, fully integrated" },
] as const;

export const TOOLS = [
  { id: "google_ads", name: "Google Ads", icon: "G", color: "#4285F4", description: "Search & display advertising" },
  { id: "meta_ads", name: "Meta Ads", icon: "M", color: "#0668E1", description: "Facebook & Instagram ads" },
  { id: "quickbooks", name: "QuickBooks", icon: "Q", color: "#2CA01C", description: "Accounting & invoicing" },
  { id: "google_workspace", name: "Google Workspace", icon: "W", color: "#EA4335", description: "Gmail, Sheets, Drive" },
  { id: "tiktok_ads", name: "TikTok Ads", icon: "T", color: "#000000", description: "Short-form video advertising" },
] as const;

export interface AutomationTemplate {
  id: string;
  name: string;
  description: string;
  time_saved: string;
  tools_needed: string[];
  category: string;
  icon: string;
}
