"use client";
import { create } from "zustand";

interface AuthState {
  ready: boolean;
  setReady: () => void;
  logout: () => void;
}

export const useAuth = create<AuthState>()((set) => ({
  ready: false,
  setReady: () => set({ ready: true }),
  logout: () => {
    sessionStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/login";
  },
}));
