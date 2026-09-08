import type { ApiErrorShape, ConversationResponse, LoginResponse, MessageResponse } from './types';
import { getToken } from '../auth/session';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: ApiErrorShape = {};
  try {
    payload = (await response.json()) as ApiErrorShape;
  } catch {
    // Use the HTTP status when the server did not return JSON.
  }
  return new ApiError(payload.detail ?? `Request failed (${response.status})`, response.status);
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

export function login(username: string, password: string): Promise<LoginResponse> {
  const body = new URLSearchParams({ username, password });
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
}

export function createConversation(): Promise<ConversationResponse> {
  return request<ConversationResponse>('/conversations', { method: 'POST' });
}

export function sendMessage(conversationId: string, content: string): Promise<MessageResponse> {
  return request<MessageResponse>(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}