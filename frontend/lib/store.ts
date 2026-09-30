"use client";
import { create } from "zustand";

interface AuthState {
  ready: boolean;
  setReady: () => void;
  logout: () => void;
  navOpen: boolean;
  setNavOpen: (v: boolean) => void;
}

export const useAuth = create<AuthState>()((set) => ({
  ready: false,
  setReady: () => set({ ready: true }),
  logout: () => {
    sessionStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/login";
  },
  navOpen: false,
  setNavOpen: (v) => set({ navOpen: v }),
}));
