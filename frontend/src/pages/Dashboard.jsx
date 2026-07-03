import { useEffect, useState } from "react";
import {
  Container,
  Grid,
  Paper,
  Typography,
} from "@mui/material";

import api from "../services/api";

export default function Dashboard() {

  const [account, setAccount] = useState({});
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);

  const loadData = async () => {
    try {
      const accountRes = await api.get("/account");
      const positionsRes = await api.get("/positions");
      const tradesRes = await api.get("/trades");

      setAccount(accountRes.data);
      setPositions(positionsRes.data);
      setTrades(tradesRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();

    const timer = setInterval(loadData, 5000);

    return () => clearInterval(timer);

  }, []);

  return (
    <Container maxWidth="xl" sx={{ mt: 4 }}>

      <Typography
        variant="h3"
        sx={{ mb: 4 }}
      >
        Apex Trader
      </Typography>

      <Grid container spacing={3}>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6">
              Equity
            </Typography>

            <Typography variant="h4">
              ${Number(account.equity || 0).toLocaleString()}
            </Typography>

          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6">
              Cash
            </Typography>

            <Typography variant="h4">
              ${Number(account.cash || 0).toLocaleString()}
            </Typography>

          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6">
              Buying Power
            </Typography>

            <Typography variant="h4">
              ${Number(account.buying_power || 0).toLocaleString()}
            </Typography>

          </Paper>
        </Grid>

      </Grid>

      <Paper sx={{ mt: 4, p: 2 }}>

        <Typography variant="h5" sx={{ mb: 2 }}>
          Open Positions
        </Typography>

        {positions.map((p) => (

          <Paper
            key={p.asset_id}
            sx={{
              mb: 1,
              p: 2
            }}
          >
            <strong>{p.symbol}</strong>

            {" • "}

            Qty: {p.qty}

            {" • "}

            Price: ${p.current_price}

            {" • "}

            P/L: ${p.unrealized_pl}

          </Paper>

        ))}

      </Paper>

      <Paper sx={{ mt: 4, p: 2 }}>

        <Typography variant="h5" sx={{ mb: 2 }}>
          Recent Trades
        </Typography>

        {trades.map((trade, index) => (

          <Paper
            key={index}
            sx={{
              mb: 1,
              p: 2
            }}
          >

            {trade.timestamp}

            <br />

            {trade.side.toUpperCase()}

            {" "}

            {trade.qty}

            {" "}

            {trade.symbol}

          </Paper>

        ))}

      </Paper>

    </Container>
  );
}