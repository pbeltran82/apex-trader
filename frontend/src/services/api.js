import axios from "axios";

// Using Vite proxy (NO hardcoded backend URL)
const API = axios.create({
  baseURL: "",
});

// -------- Core Trading Endpoints --------

export const getAccount = () => API.get("/account");

export const getPositions = () => API.get("/positions");

export const getTrades = () => API.get("/trades");

export const getExposure = () => API.get("/exposure");

// -------- Trading Action --------

export const placeTrade = (data) => API.post("/trade", data);

// -------- Market Data (optional future use) --------

export const getMarketData = (symbol) =>
  API.get(`/market/${symbol}`);

// -------- Default export --------

export default API;