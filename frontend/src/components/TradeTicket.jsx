import { useState } from "react";
import {
  Paper,
  Typography,
  TextField,
  Button,
  Box,
  Alert,
} from "@mui/material";

import { submitTrade } from "../services/api";

export default function TradeTicket({ onTrade }) {
  const [symbol, setSymbol] = useState("");
  const [qty, setQty] = useState(1);
  const [side, setSide] = useState("buy");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const handleTrade = async (tradeSide) => {
    setLoading(true);
    setMessage(null);

    try {
      const res = await submitTrade({
        symbol: symbol.toUpperCase(),
        qty: Number(qty),
        side: tradeSide,
      });

      setMessage({
        type: "success",
        text: `Order ${res.data.status} (${res.data.order_id})`,
      });

      setSymbol("");
      setQty(1);

      if (onTrade) onTrade(res.data);

    } catch (err) {
      console.error(err);

      setMessage({
        type: "error",
        text: "Trade failed. Check backend logs.",
      });
    }

    setLoading(false);
  };

  return (
    <Paper sx={{ p: 3, mt: 4 }}>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Trade Ticket
      </Typography>

      {message && (
        <Alert severity={message.type} sx={{ mb: 2 }}>
          {message.text}
        </Alert>
      )}

      <Box sx={{ display: "flex", gap: 2, mb: 2 }}>
        <TextField
          label="Symbol"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          fullWidth
        />

        <TextField
          label="Qty"
          type="number"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          sx={{ width: 120 }}
        />
      </Box>

      <Box sx={{ display: "flex", gap: 2 }}>
        <Button
          variant="contained"
          color="success"
          disabled={!symbol || loading}
          onClick={() => handleTrade("buy")}
          fullWidth
        >
          BUY
        </Button>

        <Button
          variant="contained"
          color="error"
          disabled={!symbol || loading}
          onClick={() => handleTrade("sell")}
          fullWidth
        >
          SELL
        </Button>
      </Box>
    </Paper>
  );
}