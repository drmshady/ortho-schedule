import {
  createContext,
  PropsWithChildren,
  useCallback,
  useContext,
  useMemo
} from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAuthSession,
  postAuthChangePassword,
  postAuthLogin,
  postAuthLogout,
  type Role,
  type Session
} from "../api/generated";

type LoginInput = {
  email: string;
  password: string;
};

type ChangePasswordInput = {
  currentPassword: string;
  newPassword: string;
};

type AuthContextValue = {
  session: Session | null;
  isLoading: boolean;
  login: (input: LoginInput) => Promise<Session | undefined>;
  logout: () => Promise<void>;
  changePassword: (input: ChangePasswordInput) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({
    queryKey: ["auth", "session"],
    queryFn: async () => {
      const response = await getAuthSession({ throwOnError: false });
      return response.data ?? null;
    }
  });

  const loginMutation = useMutation({
    mutationFn: async (input: LoginInput) => {
      const response = await postAuthLogin({
        body: { email: input.email, password: input.password },
        throwOnError: true
      });
      return response.data;
    },
    onSuccess: (session) => queryClient.setQueryData(["auth", "session"], session)
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      await postAuthLogout({ throwOnError: false });
    },
    onSuccess: () => queryClient.setQueryData(["auth", "session"], null)
  });

  const changePasswordMutation = useMutation({
    mutationFn: async (input: ChangePasswordInput) => {
      await postAuthChangePassword({
        body: {
          current_password: input.currentPassword,
          new_password: input.newPassword
        },
        throwOnError: true
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["auth", "session"] });
    }
  });

  const value = useMemo<AuthContextValue>(
    () => ({
      session: sessionQuery.data ?? null,
      isLoading: sessionQuery.isLoading,
      login: loginMutation.mutateAsync,
      logout: logoutMutation.mutateAsync,
      changePassword: changePasswordMutation.mutateAsync
    }),
    [
      changePasswordMutation.mutateAsync,
      loginMutation.mutateAsync,
      logoutMutation.mutateAsync,
      sessionQuery.data,
      sessionQuery.isLoading
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}

export function RequireAuth({ roles }: { roles?: Role[] }) {
  const { session, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) {
    return <main className="min-h-screen bg-zinc-50" />;
  }
  if (!session) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (session.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  if (roles && (!session.role || !roles.includes(session.role))) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

export function usePostLoginRedirect() {
  const navigate = useNavigate();
  const location = useLocation();
  return useCallback(
    (session: Session | undefined) => {
      if (session?.must_change_password) {
        navigate("/change-password", { replace: true });
        return;
      }
      const state = location.state as { from?: Location } | null;
      navigate(state?.from?.pathname ?? "/", { replace: true });
    },
    [location.state, navigate]
  );
}
