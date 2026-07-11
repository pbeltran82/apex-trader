import api.app as api_module
from api.intelligence import install_intelligence
from api.market_data import install_market_data
from api.risk_gate import install_risk_enforcement, register_risk_gate
from api.decision_engine import register_decision_engine
from api.runtime_hardening import install_runtime_hardening

app = api_module.app

install_intelligence(api_module)
install_runtime_hardening(api_module)
install_risk_enforcement(api_module)
install_market_data(api_module)
register_risk_gate(app)
register_decision_engine(app)
