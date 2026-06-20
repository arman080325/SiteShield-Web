import { api } from "./client";

export function signup(email, password) {
  return api.post("/auth/signup", { email, password });
}

export function login(email, password) {
  // Backend expects `username` (it's the OAuth2 form field) — we pass the email
  return api.postForm("/auth/login", { username: email, password });
}

export function getMe() {
  return api.get("/auth/me");
}