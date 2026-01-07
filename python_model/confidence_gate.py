"""
Confidence Gate - Hierarchical Confidence Rules
Centralized confidence gating for multi-timeframe architecture.

Implements hierarchical confidence gates:
- IF D1 confidence < D1_MIN → NO_TRADE
- IF H4/H1 confirmation != CONFIRM → NO_TRADE
- IF entry conditions not met → NO_TRADE
- ELSE → TRADE_ALLOWED

Each layer logs:
- Raw confidence
- Calibrated confidence
- Drift status
"""

from pathlib import Path
import json
from datetime import datetime


def load_config():
    """Load configuration"""
    path = Path(__file__).parent / 'config.json'
    with open(path, 'r') as f:
        return json.load(f)


class ConfidenceGate:
    """
    Hierarchical confidence gate for multi-timeframe trading system.
    
    Enforces strict confidence requirements at each layer.
    """
    
    def __init__(self, config=None):
        """
        Initialize confidence gate.
        
        Args:
            config: Configuration dict
        """
        self.config = config or load_config()
        
        # Load confidence thresholds
        self.gate_config = self.config.get('confidence_gates', {
            'd1_min_confidence': 0.55,
            'h4h1_min_confidence': 0.55,
            'entry_min_confidence': 0.60,
            'max_calibration_drift': 0.15,
            'block_on_drift': True
        })
    
    def check_d1_gate(self, d1_bias_result):
        """
        Check D1 bias confidence gate.
        
        Args:
            d1_bias_result: Result from D1BiasModel.predict_bias()
            
        Returns:
            dict: {
                'passed': bool,
                'reason': str,
                'confidence': float,
                'threshold': float
            }
        """
        min_conf = self.gate_config.get('d1_min_confidence', 0.55)
        confidence = d1_bias_result.get('confidence', 0.0)
        bias = d1_bias_result.get('bias', 'NEUTRAL')
        
        # Check calibration drift
        drift_check = self._check_calibration_drift(d1_bias_result)
        if drift_check['block']:
            return {
                'passed': False,
                'reason': f"Calibration drift exceeds threshold: {drift_check['drift']:.2%}",
                'confidence': confidence,
                'threshold': min_conf,
                'drift': drift_check['drift']
            }
        
        # Check minimum confidence
        if confidence < min_conf:
            return {
                'passed': False,
                'reason': f"D1 confidence {confidence:.2%} below minimum {min_conf:.2%}",
                'confidence': confidence,
                'threshold': min_conf
            }
        
        # Check if bias is NEUTRAL
        if bias == 'NEUTRAL':
            return {
                'passed': False,
                'reason': 'D1 bias is NEUTRAL',
                'confidence': confidence,
                'threshold': min_conf
            }
        
        return {
            'passed': True,
            'reason': f"D1 bias {bias} with confidence {confidence:.2%}",
            'confidence': confidence,
            'threshold': min_conf
        }
    
    def check_h4h1_gate(self, h4h1_confirmation_result):
        """
        Check H4/H1 confirmation gate.
        
        Args:
            h4h1_confirmation_result: Result from H4H1ConfirmationModel.predict_confirmation()
            
        Returns:
            dict: {
                'passed': bool,
                'reason': str,
                'confirmation': str,
                'confidence': float,
                'threshold': float
            }
        """
        min_conf = self.gate_config.get('h4h1_min_confidence', 0.55)
        confirmation = h4h1_confirmation_result.get('confirmation', 'NEUTRAL')
        confidence = h4h1_confirmation_result.get('confidence', 0.0)
        
        # Check calibration drift for H4 and H1
        h4_result = h4h1_confirmation_result.get('h4_result', {})
        h1_result = h4h1_confirmation_result.get('h1_result', {})
        
        h4_drift = self._check_calibration_drift_simple(h4_result)
        h1_drift = self._check_calibration_drift_simple(h1_result)
        
        max_drift = max(h4_drift.get('drift', 0), h1_drift.get('drift', 0))
        if max_drift > self.gate_config.get('max_calibration_drift', 0.15):
            return {
                'passed': False,
                'reason': f"H4/H1 calibration drift {max_drift:.2%} exceeds threshold",
                'confirmation': confirmation,
                'confidence': confidence,
                'threshold': min_conf,
                'drift': max_drift
            }
        
        # Check confirmation status
        if confirmation != 'CONFIRM':
            return {
                'passed': False,
                'reason': f"H4/H1 confirmation is {confirmation}, required CONFIRM",
                'confirmation': confirmation,
                'confidence': confidence,
                'threshold': min_conf
            }
        
        # Check minimum confidence
        if confidence < min_conf:
            return {
                'passed': False,
                'reason': f"H4/H1 confidence {confidence:.2%} below minimum {min_conf:.2%}",
                'confirmation': confirmation,
                'confidence': confidence,
                'threshold': min_conf
            }
        
        return {
            'passed': True,
            'reason': f"H4/H1 CONFIRM with confidence {confidence:.2%}",
            'confirmation': confirmation,
            'confidence': confidence,
            'threshold': min_conf
        }
    
    def check_entry_gate(self, entry_result):
        """
        Check entry signal gate.
        
        Args:
            entry_result: Result from M15M5EntryEngine.detect_entry()
            
        Returns:
            dict: {
                'passed': bool,
                'reason': str,
                'entry_signal': str,
                'confidence': float,
                'threshold': float
            }
        """
        min_conf = self.gate_config.get('entry_min_confidence', 0.60)
        entry_signal = entry_result.get('entry_signal', 'NONE')
        confidence = entry_result.get('confidence', 0.0)
        
        # Check if entry signal exists
        if entry_signal == 'NONE':
            return {
                'passed': False,
                'reason': entry_result.get('reason', 'No entry signal detected'),
                'entry_signal': entry_signal,
                'confidence': confidence,
                'threshold': min_conf
            }
        
        # Check minimum confidence
        if confidence < min_conf:
            return {
                'passed': False,
                'reason': f"Entry confidence {confidence:.2%} below minimum {min_conf:.2%}",
                'entry_signal': entry_signal,
                'confidence': confidence,
                'threshold': min_conf
            }
        
        return {
            'passed': True,
            'reason': f"Entry signal {entry_signal} with confidence {confidence:.2%}",
            'entry_signal': entry_signal,
            'confidence': confidence,
            'threshold': min_conf
        }
    
    def check_all_gates(self, d1_bias, h4h1_confirmation, entry_signal):
        """
        Check all confidence gates in sequence.
        
        Args:
            d1_bias: D1 bias result
            h4h1_confirmation: H4/H1 confirmation result
            entry_signal: Entry signal result
            
        Returns:
            dict: {
                'trade_allowed': bool,
                'block_reason': str (if blocked),
                'gate_results': {
                    'd1': dict,
                    'h4h1': dict,
                    'entry': dict
                },
                'timestamp': str
            }
        """
        gate_results = {}
        
        # Gate 1: D1 Bias
        d1_gate = self.check_d1_gate(d1_bias)
        gate_results['d1'] = d1_gate
        
        if not d1_gate['passed']:
            return {
                'trade_allowed': False,
                'block_reason': f"D1 Gate: {d1_gate['reason']}",
                'gate_results': gate_results,
                'timestamp': datetime.now().isoformat()
            }
        
        # Gate 2: H4/H1 Confirmation
        h4h1_gate = self.check_h4h1_gate(h4h1_confirmation)
        gate_results['h4h1'] = h4h1_gate
        
        if not h4h1_gate['passed']:
            return {
                'trade_allowed': False,
                'block_reason': f"H4/H1 Gate: {h4h1_gate['reason']}",
                'gate_results': gate_results,
                'timestamp': datetime.now().isoformat()
            }
        
        # Gate 3: Entry Signal
        entry_gate = self.check_entry_gate(entry_signal)
        gate_results['entry'] = entry_gate
        
        if not entry_gate['passed']:
            return {
                'trade_allowed': False,
                'block_reason': f"Entry Gate: {entry_gate['reason']}",
                'gate_results': gate_results,
                'timestamp': datetime.now().isoformat()
            }
        
        # All gates passed
        return {
            'trade_allowed': True,
            'block_reason': None,
            'gate_results': gate_results,
            'timestamp': datetime.now().isoformat()
        }
    
    def _check_calibration_drift(self, result):
        """
        Check calibration drift for a result.
        
        Args:
            result: Result dict with 'raw_probability' and 'calibrated_probability'
            
        Returns:
            dict: {
                'block': bool,
                'drift': float
            }
        """
        raw_prob = result.get('raw_probability', 0.5)
        calibrated_prob = result.get('calibrated_probability', 0.5)
        
        drift = abs(raw_prob - calibrated_prob)
        max_drift = self.gate_config.get('max_calibration_drift', 0.15)
        block_on_drift = self.gate_config.get('block_on_drift', True)
        
        return {
            'block': block_on_drift and drift > max_drift,
            'drift': drift
        }
    
    def _check_calibration_drift_simple(self, result):
        """
        Simplified drift check for H4/H1 results.
        """
        # H4/H1 results may not have raw/calibrated probabilities
        # Return no drift if not available
        if 'raw_probability' not in result or 'calibrated_probability' not in result:
            return {'drift': 0.0, 'block': False}
        
        return self._check_calibration_drift(result)


def main():
    """Test confidence gate"""
    from d1_bias_model import D1BiasModel
    from h4h1_confirmation_model import H4H1ConfirmationModel
    from m15m5_entry_engine import M15M5EntryEngine
    
    # Get all results
    d1_model = D1BiasModel()
    d1_bias = d1_model.predict_bias()
    
    conf_model = H4H1ConfirmationModel()
    confirmation = conf_model.predict_confirmation(d1_bias)
    
    entry_engine = M15M5EntryEngine()
    entry = entry_engine.detect_entry(d1_bias, confirmation)
    
    # Check gates
    gate = ConfidenceGate()
    result = gate.check_all_gates(d1_bias, confirmation, entry)
    
    print("\n" + "="*60)
    print("CONFIDENCE GATE TEST")
    print("="*60)
    print(f"Trade Allowed: {result['trade_allowed']}")
    if result['block_reason']:
        print(f"Block Reason: {result['block_reason']}")
    print("\nGate Results:")
    for gate_name, gate_result in result['gate_results'].items():
        status = "✅ PASS" if gate_result['passed'] else "❌ FAIL"
        print(f"  {gate_name.upper()}: {status} - {gate_result['reason']}")
    print("="*60)


if __name__ == "__main__":
    main()



