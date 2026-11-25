import {
  AuthResponse,
  DashboardSummary,
  EngineSettings,
  HealthStatus,
  PaginatedTransactions,
  StatementItem,
  StatementResults,
  User,
} from './types';

const BASE_API = '/api/v1';

export const authStorage = {
  getToken: (): string | null => localStorage.getItem('salarylens_token'),
  setToken: (token: string) => localStorage.setItem('salarylens_token', token),
  clearToken: () => localStorage.removeItem('salarylens_token'),
  getUser: (): User | null => {
    const raw = localStorage.getItem('salarylens_user');
    return raw ? JSON.parse(raw) : null;
  },
  setUser: (u: User) => localStorage.setItem('salarylens_user', JSON.stringify(u)),
  clearUser: () => localStorage.removeItem('salarylens_user'),
};

async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = authStorage.getToken();
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${BASE_API}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    authStorage.clearToken();
    authStorage.clearUser();
    // Dispatch custom event for auth reset
    window.dispatchEvent(new Event('auth:unauthorized'));
    throw new Error('Session expired or unauthorized. Please log in.');
  }

  if (!response.ok) {
    let errorDetail = `Request failed (${response.status})`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // Health
  getHealth: async (): Promise<HealthStatus> => {
    return apiFetch<HealthStatus>('/health');
  },

  // Auth
  register: async (payload: {
    email: string;
    password: string;
    full_name: string;
    organization_name: string;
    role: string;
  }): Promise<AuthResponse> => {
    const data = await apiFetch<AuthResponse>('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    authStorage.setToken(data.access_token);
    return data;
  },

  login: async (payload: { email: string; password: string }): Promise<AuthResponse> => {
    const data = await apiFetch<AuthResponse>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    authStorage.setToken(data.access_token);
    return data;
  },

  getMe: async (): Promise<User> => {
    const user = await apiFetch<User>('/auth/me');
    authStorage.setUser(user);
    return user;
  },

  logout: () => {
    authStorage.clearToken();
    authStorage.clearUser();
  },

  // Dashboard
  getDashboardSummary: async (): Promise<DashboardSummary> => {
    return apiFetch<DashboardSummary>('/dashboard/summary');
  },

  // Statements
  getStatements: async (): Promise<StatementItem[]> => {
    return apiFetch<StatementItem[]>('/statements');
  },

  getStatementStatus: async (statementId: string): Promise<StatementItem> => {
    return apiFetch<StatementItem>(`/statements/${statementId}/status`);
  },

  getStatementResults: async (statementId: string): Promise<StatementResults> => {
    return apiFetch<StatementResults>(`/statements/${statementId}/results`);
  },

  getStatementTransactions: async (
    statementId: string,
    page: number = 1,
    pageSize: number = 50,
    includedOnly?: boolean
  ): Promise<PaginatedTransactions> => {
    let url = `/statements/${statementId}/transactions?page=${page}&page_size=${pageSize}`;
    if (includedOnly !== undefined) {
      url += `&included_only=${includedOnly}`;
    }
    return apiFetch<PaginatedTransactions>(url);
  },

  uploadStatement: async (file: File, durationMonths?: number): Promise<StatementItem> => {
    const token = authStorage.getToken();
    const formData = new FormData();
    formData.append('file', file);
    if (durationMonths) {
      formData.append('duration_months', durationMonths.toString());
    }

    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_API}/statements`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const errJson = await response.json().catch(() => ({}));
      throw new Error(errJson.detail || 'Upload failed');
    }

    return response.json();
  },

  reanalyzeStatement: async (statementId: string): Promise<StatementItem> => {
    return apiFetch<StatementItem>(`/statements/${statementId}/analyze`, {
      method: 'POST',
    });
  },

  submitReview: async (
    statementId: string,
    review: {
      status: 'approved' | 'rejected' | 'adjusted';
      confirmed_employer?: string;
      confirmed_transaction_ids?: string[];
      review_notes?: string;
    }
  ) => {
    return apiFetch(`/statements/${statementId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(review),
    });
  },

  downloadWorkbookUrl: (statementId: string): string => {
    return `${BASE_API}/statements/${statementId}/download`;
  },

  downloadWorkbook: async (statementId: string, filename: string) => {
    const token = authStorage.getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`${BASE_API}/statements/${statementId}/download`, {
      headers,
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || 'Workbook generation in progress or download failed.');
    }

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.setAttribute('download', filename || `SalaryLens_Analysis.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  },

  deleteStatement: async (statementId: string): Promise<{ success: boolean; message: string }> => {
    return apiFetch<{ success: boolean; message: string }>(`/statements/${statementId}`, {
      method: 'DELETE',
    });
  },

  getStatementLogs: async (statementId: string): Promise<{
    statement_id: string;
    status: string;
    filename: string;
    logs: Array<{
      timestamp: string;
      stage: string;
      level: string;
      title: string;
      message: string;
      metadata?: Record<string, any>;
    }>;
  }> => {
    return apiFetch(`/statements/${statementId}/logs`);
  },

  getEngineSettings: async (): Promise<EngineSettings> => {
    return apiFetch<EngineSettings>('/admin/engine-settings');
  },

  updateEngineSettings: async (payload: Partial<EngineSettings>): Promise<EngineSettings> => {
    return apiFetch<EngineSettings>('/admin/engine-settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
};

