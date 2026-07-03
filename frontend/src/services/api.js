import axios from "axios";

const API_BASE = "https://ubiquitous-capybara-v6gj596vr473xpwg-8000.app.github.dev";

const api = axios.create({
  baseURL: API_BASE,
});

export const getAccount = () => api.get("/account");
export const getPositions = () => api.get("/positions");
export const getTrades = () => api.get("/trades");

export const submitTrade = (data) =>
  api.post("/trade", data);

export default api;