export type UserRole = 'employee' | 'l1' | 'l2' | 'support_lead' | 'admin';

export interface AuthUser {
  email: string;
  role: UserRole;
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  user: AuthUser;
}

export interface ApiErrorShape {
  detail?: string;
}

export interface ConversationResponse {
  id: string;
  status: string;
}

export interface AgentMessage {
  sender: string;
  content: string;
}

export interface MessageResponse {
  messages: AgentMessage[];
  status?: string;
  state?: WorkflowState;
}

export interface WorkflowState {
  category?: string;
  status?: string;
  escalate?: boolean;
  evidence?: unknown[];
  tool_history?: string[];
}