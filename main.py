from api.app import app
from api.risk_gate import register_risk_gate

register_risk_gate(app)
