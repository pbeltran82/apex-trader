from api.app import app
from api.risk_gate import register_risk_gate
from api.decision_engine import register_decision_engine

register_risk_gate(app)
register_decision_engine(app)
