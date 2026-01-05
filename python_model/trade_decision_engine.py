"""
Trade Decision Engine - Final Arbiter
Final decision maker that cannot be overridden.

Enforces:
- Higher timeframes give permission
- Lower timeframes ask for entry
- No permission = no trade

Behavioral Rules:
- NO_TRADE is a valid success outcome
- Capital protection overrides signal frequency
- If data freshness, confidence, or alignment is uncertain → block trade
- Deterministic decisions only (same input → same output)
"""

from pathlib import Path
import json
from datetime import datetime

from d1_bias_model import D1BiasModel
from h4h1_confirmation_model import H4H1ConfirmationModel
from m15m5_entry_engine import M15M5EntryEngine
from confidence_gate import ConfidenceGate


def load_config():
    """Load configuration"""
    path = Path(__file__).parent / 'config.json'
    with open(path, 'r') as f:
        return json.load(f)


class TradeDecisionEngine:
    """
    Final trade decision engine - cannot be overridden.
    
    Implements hierarchical decision flow:
    1. D1 Bias Model (permission layer)
    2. H4/H1 Confirmation Model (confirmation layer)
    3. M15/M5 Entry Engine (execution layer)
    4. Confidence Gate (validation layer)
    5. Final Decision (arbitration layer)
    """
    
    def __init__(self, config=None):
        """
        Initialize trade decision engine.
        
        Args:
            config: Configuration dict
        """
        self.config = config or load_config()
        
        # Initialize components
        self.d1_model = D1BiasModel(config)
        self.h4h1_model = H4H1ConfirmationModel(config)
        self.entry_engine = M15M5EntryEngine(config)
        self.confidence_gate = ConfidenceGate(config)
        
        # Decision history
        self.decision_history = []
    
    def make_decision(self, update_data=True):
        """
        Make final trade decision using hierarchical flow.
        
        Args:
            update_data: If True, fetch latest data before decision
            
        Returns:
            dict: {
                'decision': 'TRADE' | 'NO_TRADE',
                'direction': 'LONG' | 'SHORT' | None,
                'confidence': float,
                'layers': {
                    'd1_bias': dict,
                    'h4h1_confirmation': dict,
                    'entry_signal': dict,
                    'confidence_gate': dict
                },
                'reason': str,
                'timestamp': str
            }
        """
        try:
            # Layer 1: D1 Bias (Permission Layer)
            d1_bias = self.d1_model.predict_bias(update_data=update_data)
            
            # If D1 bias is NEUTRAL or low confidence, block immediately
            if d1_bias.get('bias') == 'NEUTRAL' or d1_bias.get('confidence', 0) < 0.5:
                return self._create_no_trade_decision(
                    reason=f"D1 bias is {d1_bias.get('bias')} with confidence {d1_bias.get('confidence', 0):.2%}",
                    d1_bias=d1_bias
                )
            
            # Layer 2: H4/H1 Confirmation (Confirmation Layer)
            h4h1_confirmation = self.h4h1_model.predict_confirmation(
                d1_bias, 
                update_data=update_data
            )
            
            # If confirmation is not CONFIRM, block
            if h4h1_confirmation.get('confirmation') != 'CONFIRM':
                return self._create_no_trade_decision(
                    reason=f"H4/H1 confirmation is {h4h1_confirmation.get('confirmation')}",
                    d1_bias=d1_bias,
                    h4h1_confirmation=h4h1_confirmation
                )
            
            # Layer 3: M15/M5 Entry (Execution Layer)
            entry_signal = self.entry_engine.detect_entry(
                d1_bias,
                h4h1_confirmation,
                update_data=update_data
            )
            
            # If no entry signal, block
            if entry_signal.get('entry_signal') == 'NONE':
                return self._create_no_trade_decision(
                    reason=entry_signal.get('reason', 'No entry signal detected'),
                    d1_bias=d1_bias,
                    h4h1_confirmation=h4h1_confirmation,
                    entry_signal=entry_signal
                )
            
            # Layer 4: Confidence Gate (Validation Layer)
            gate_result = self.confidence_gate.check_all_gates(
                d1_bias,
                h4h1_confirmation,
                entry_signal
            )
            
            # If gate blocks, no trade
            if not gate_result['trade_allowed']:
                return self._create_no_trade_decision(
                    reason=gate_result['block_reason'],
                    d1_bias=d1_bias,
                    h4h1_confirmation=h4h1_confirmation,
                    entry_signal=entry_signal,
                    confidence_gate=gate_result
                )
            
            # Layer 5: Final Decision (All layers passed)
            direction = entry_signal['entry_signal']  # LONG or SHORT
            confidence = min(
                d1_bias.get('confidence', 0),
                h4h1_confirmation.get('confidence', 0),
                entry_signal.get('confidence', 0)
            )
            
            decision = {
                'decision': 'TRADE',
                'direction': direction,
                'confidence': float(confidence),
                'layers': {
                    'd1_bias': d1_bias,
                    'h4h1_confirmation': h4h1_confirmation,
                    'entry_signal': entry_signal,
                    'confidence_gate': gate_result
                },
                'reason': f"All layers passed: D1={d1_bias['bias']}, "
                         f"Confirmation={h4h1_confirmation['confirmation']}, "
                         f"Entry={entry_signal['entry_signal']}",
                'timestamp': datetime.now().isoformat()
            }
            
            # Log decision
            self.decision_history.append(decision)
            
            return decision
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._create_no_trade_decision(
                reason=f"Error in decision engine: {str(e)}",
                error=str(e)
            )
    
    def _create_no_trade_decision(self, reason, **layers):
        """
        Create a NO_TRADE decision with all layer information.
        
        Args:
            reason: Reason for NO_TRADE
            **layers: Layer results (d1_bias, h4h1_confirmation, etc.)
            
        Returns:
            dict: NO_TRADE decision
        """
        decision = {
            'decision': 'NO_TRADE',
            'direction': None,
            'confidence': 0.0,
            'layers': layers,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }
        
        # Log decision
        self.decision_history.append(decision)
        
        return decision
    
    def get_decision_summary(self, decision):
        """
        Get human-readable summary of decision.
        
        Args:
            decision: Decision dict from make_decision()
            
        Returns:
            str: Formatted summary
        """
        lines = []
        lines.append("="*70)
        lines.append("TRADE DECISION SUMMARY")
        lines.append("="*70)
        lines.append(f"Decision: {decision['decision']}")
        
        if decision['decision'] == 'TRADE':
            lines.append(f"Direction: {decision['direction']}")
            lines.append(f"Confidence: {decision['confidence']:.2%}")
        else:
            lines.append(f"Reason: {decision['reason']}")
        
        lines.append("\nLayer Details:")
        
        layers = decision.get('layers', {})
        
        if 'd1_bias' in layers:
            d1 = layers['d1_bias']
            lines.append(f"  D1 Bias: {d1.get('bias', 'N/A')} "
                       f"({d1.get('confidence', 0):.2%})")
        
        if 'h4h1_confirmation' in layers:
            conf = layers['h4h1_confirmation']
            lines.append(f"  H4/H1 Confirmation: {conf.get('confirmation', 'N/A')} "
                       f"({conf.get('confidence', 0):.2%})")
        
        if 'entry_signal' in layers:
            entry = layers['entry_signal']
            lines.append(f"  Entry Signal: {entry.get('entry_signal', 'N/A')} "
                       f"({entry.get('confidence', 0):.2%})")
            if 'entry_type' in entry:
                lines.append(f"    Type: {entry['entry_type']}")
        
        if 'confidence_gate' in layers:
            gate = layers['confidence_gate']
            lines.append(f"  Confidence Gate: {'PASSED' if gate.get('trade_allowed') else 'BLOCKED'}")
            if gate.get('block_reason'):
                lines.append(f"    Reason: {gate['block_reason']}")
        
        lines.append("="*70)
        
        return "\n".join(lines)
    
    def get_recent_decisions(self, count=10):
        """Get recent decision history"""
        return self.decision_history[-count:]


def main():
    """Test trade decision engine"""
    engine = TradeDecisionEngine()
    decision = engine.make_decision()
    
    print(engine.get_decision_summary(decision))


if __name__ == "__main__":
    main()

