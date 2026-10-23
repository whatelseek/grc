export type Role = "admin" | "consultant" | "respondent";
export type SurveyStatus = "draft" | "submitted" | "reviewed";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  client_ids: string[];
}

export interface Client {
  id: string;
  name: string;
  code: string | null;
  notes: string;
  is_active: boolean;
  system_count: number;
}

export interface System {
  id: string;
  client_id: string;
  name: string;
  business_owner: string;
  it_owner: string;
  description: string;
  survey_count: number;
}

export interface Answer {
  question_code: number;
  text: string | null;
  level: string | null;
  selections: string[] | null;
}

export interface Issue {
  code: number;
  severity: "missing" | "warning";
  message: string;
}

export interface Progress {
  required_total: number;
  required_filled: number;
  optional_total: number;
  warnings: number;
  complete: boolean;
}

export interface SeriesRow {
  code: number;
  period_label: string;
  period_hours: number;
  weight: number;
  level: string | null;
  weighted_score: number | null;
}

export interface Series {
  criticality: number;
  answered: number;
  total: number;
  rows: SeriesRow[];
}

export interface Result {
  overall_criticality: number | null;
  criticality_by_type: Record<string, { availability?: Series; integrity?: Series }>;
  mtpd_hours: number | null;
  mtpd_beyond_scale: boolean;
  rto_hours: number | null;
  rpo_hours: number | null;
  issues: Issue[];
  progress: Progress;
}

export interface Survey {
  id: string;
  system_id: string;
  system_name: string | null;
  client_id: string | null;
  client_name: string | null;
  status: SurveyStatus;
  template_version: string;
  assignee_id: string | null;
  updated_at: string;
  submitted_at: string | null;
}

export interface SurveyDetail extends Survey {
  answers: Answer[];
  result: Result;
}

export interface TemplateQuestion {
  code: number;
  part: number;
  kind: "text" | "textarea" | "select" | "select_text" | "multiselect3";
  text: string;
  help: string | null;
  option_list: string | null;
  required: boolean;
}

export interface MatrixRow {
  code: number;
  label: string;
  period_label: string;
  period_hours: number;
  weight: number;
}

export interface Matrix {
  part: number;
  damage_type: string;
  prompt: string;
  descriptions: { area: string | null; levels: Record<string, string | null> }[];
  rows: MatrixRow[];
}

export interface Template {
  title: string;
  notes: string;
  instructions: string[];
  levels: string[];
  level_scores: Record<string, number>;
  option_lists: Record<string, string[]>;
  parts: { number: number; title: string }[];
  questions: TemplateQuestion[];
  matrices: Matrix[];
  calculation_notes: string;
}

export interface DashboardRow {
  survey_id: string;
  client_id: string;
  client_name: string;
  system_id: string;
  system_name: string;
  business_owner: string;
  it_owner: string;
  status: SurveyStatus;
  overall_criticality: number | null;
  mtpd_hours: number | null;
  rto_hours: number | null;
  rpo_hours: number | null;
  stated_mtpd: string | null;
  stated_rto: string | null;
  stated_rpo: string | null;
  current_rto: string | null;
  current_rpo: string | null;
  required_filled: number;
  required_total: number;
  warnings: number;
  updated_at: string;
}

export type ImplementationStatus =
  | "not_implemented"
  | "partial"
  | "implemented"
  | "not_applicable";
export type Priority = "low" | "medium" | "high";
export type AssessmentStatus = "draft" | "in_progress" | "completed";

export interface Safeguard {
  id: string;
  title: string;
  description: string;
  asset_class: string;
  security_function: string;
  ig: 1 | 2 | 3;
}

export interface Control {
  number: string;
  title: string;
  description: string;
  safeguards: Safeguard[];
}

export interface Framework {
  framework: string;
  version: string;
  title: string;
  source: string;
  asset_classes: string[];
  security_functions: string[];
  implementation_groups: { level: number; title: string; description: string }[];
  controls: Control[];
}

export interface EvidenceFile {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface AssessmentItem {
  safeguard_id: string;
  status: ImplementationStatus;
  owner: string;
  due_date: string | null;
  priority: Priority | null;
  notes: string;
  evidence: EvidenceFile[];
}

export interface Bucket {
  implementation: number | null;
  in_scope: number;
  counted: number;
  implemented: number;
  partial: number;
  not_implemented: number;
  not_applicable: number;
}

export interface Gap {
  safeguard_id: string;
  control: string;
  control_title: string;
  title: string;
  ig: 1 | 2 | 3;
  security_function: string;
  asset_class: string;
  status: ImplementationStatus;
  owner: string;
  due_date: string | null;
  priority: Priority | null;
  notes: string;
  evidence_count: number;
}

export interface AssessmentResult {
  target_ig: number;
  overall: Bucket;
  implementation_groups: Record<string, Bucket & { level: number }>;
  by_control: (Bucket & { control: string })[];
  by_function: (Bucket & { security_function: string })[];
  by_asset_class: (Bucket & { asset_class: string })[];
  gaps: Gap[];
  progress: { in_scope: number; assessed: number; answered_total: number; complete: boolean };
}

export interface Assessment {
  id: string;
  client_id: string;
  client_name: string | null;
  framework: string;
  framework_version: string;
  name: string;
  target_ig: number;
  status: AssessmentStatus;
  assessor_id: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  implementation: number | null;
  gaps_open: number;
}

export interface AssessmentDetail extends Assessment {
  items: AssessmentItem[];
  result: AssessmentResult;
}
