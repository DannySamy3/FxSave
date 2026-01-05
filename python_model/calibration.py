"""
Confidence Calibration Module (HARDENED)
Maps raw model probabilities to realistic probabilities using Isotonic Regression.
Goal: Ensure 80% confidence actually means ~80% win rate.

FIXES APPLIED:
- Added calibration drift warnings
- Added validation on load
- Added fallback handling with warnings
- Added confidence change monitoring
"""
import numpy as np
import pickle
import os
import warnings
from sklearn.isotonic import IsotonicRegression

# Maximum acceptable drift between raw and calibrated probability
MAX_CALIBRATION_DRIFT = 0.15  # 15%


class CalibrationWarning(UserWarning):
    """Custom warning for calibration issues"""
    pass


class ModelCalibrator:
    def __init__(self, timeframe):
        self.timeframe = timeframe
        self.isotonic = IsotonicRegression(out_of_bounds='clip')
        self.is_fitted = False
        self.calibration_stats = {}  # Store stats for monitoring
        
    def fit(self, raw_probs, true_labels):
        """
        Fit calibration on Out-Of-Sample predictions.
        raw_probs: array of probability for class 1 (UP)
        true_labels: array of 0s and 1s
        
        IMPORTANT: raw_probs must come from the SAME model that will be used
        for production inference to avoid distribution mismatch.
        """
        if len(raw_probs) < 50:
            warnings.warn(
                f"Calibrator {self.timeframe}: Only {len(raw_probs)} samples. "
                "Minimum 50 recommended for reliable calibration.",
                CalibrationWarning
            )
            if len(raw_probs) < 20:
                print(f"  ⚠️ CRITICAL: Not enough samples to calibrate {self.timeframe}")
                return False
        
        # Store raw probs for diagnostics
        self.calibration_stats = {
            'n_samples': len(raw_probs),
            'raw_mean': float(np.mean(raw_probs)),
            'raw_std': float(np.std(raw_probs)),
            'true_rate': float(np.mean(true_labels)),
        }
            
        self.isotonic.fit(raw_probs, true_labels)
        self.is_fitted = True
        
        # Calculate calibration quality metrics
        calibrated = self.isotonic.predict(raw_probs)
        self.calibration_stats['calib_mean'] = float(np.mean(calibrated))
        self.calibration_stats['calib_std'] = float(np.std(calibrated))
        self.calibration_stats['mean_drift'] = abs(
            self.calibration_stats['raw_mean'] - self.calibration_stats['calib_mean']
        )
        
        # Warn if calibration significantly shifts probabilities
        if self.calibration_stats['mean_drift'] > MAX_CALIBRATION_DRIFT:
            warnings.warn(
                f"Calibrator {self.timeframe}: Large mean drift detected "
                f"({self.calibration_stats['mean_drift']:.2%}). "
                "Model may be poorly calibrated or have distribution issues.",
                CalibrationWarning
            )
        
        print(f"  ✓ Calibrator fitted: {len(raw_probs)} samples, "
              f"drift={self.calibration_stats['mean_drift']:.2%}")
        
        return True
        
    def calibrate(self, raw_prob, warn_on_drift=True):
        """
        Input: Raw probability (0.0 - 1.0)
        Output: Calibrated probability (0.0 - 1.0), drift_warning (bool)
        
        Returns tuple: (calibrated_prob, has_drift_warning)
        """
        if not self.is_fitted:
            warnings.warn(
                f"Calibrator {self.timeframe}: Not fitted! Returning raw probability.",
                CalibrationWarning
            )
            return raw_prob, True  # Return with warning flag
            
        # Isotonic expects array-like
        calibrated = self.isotonic.predict([raw_prob])[0]
        calibrated = float(calibrated)
        
        # Check for excessive drift on this specific prediction
        drift = abs(calibrated - raw_prob)
        has_drift_warning = drift > MAX_CALIBRATION_DRIFT
        
        if has_drift_warning and warn_on_drift:
            warnings.warn(
                f"Calibrator {self.timeframe}: Large drift on prediction "
                f"(raw={raw_prob:.3f}, calib={calibrated:.3f}, drift={drift:.2%})",
                CalibrationWarning
            )
        
        return calibrated, has_drift_warning
    
    def calibrate_simple(self, raw_prob):
        """
        Simple interface - returns only the calibrated probability.
        Use when drift warning is not needed.
        """
        result, _ = self.calibrate(raw_prob, warn_on_drift=False)
        return result
        
    def save(self, directory="."):
        if not self.is_fitted:
            print(f"  ⚠️ Cannot save unfitted calibrator for {self.timeframe}")
            return False
            
        path = os.path.join(directory, f'calibrator_{self.timeframe}.pkl')
        
        # Save both isotonic and stats
        save_data = {
            'isotonic': self.isotonic,
            'stats': self.calibration_stats,
            'timeframe': self.timeframe,
            'version': '2.0'
        }
        
        with open(path, 'wb') as f:
            pickle.dump(save_data, f)
        
        return True
            
    def load(self, directory="."):
        """
        Load calibrator from disk with validation.
        Returns True if loaded successfully, False otherwise.
        """
        path = os.path.join(directory, f'calibrator_{self.timeframe}.pkl')
        
        if not os.path.exists(path):
            warnings.warn(
                f"Calibrator file not found: {path}. "
                "Using uncalibrated probabilities.",
                CalibrationWarning
            )
            return False
        
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
            
            # Handle both old and new format
            if isinstance(data, dict) and 'isotonic' in data:
                # New format with stats
                self.isotonic = data['isotonic']
                self.calibration_stats = data.get('stats', {})
            else:
                # Old format - just the isotonic regressor
                self.isotonic = data
                self.calibration_stats = {}
            
            self.is_fitted = True
            
            # Validate the loaded calibrator
            if not self._validate_calibrator():
                return False
                
            return True
            
        except Exception as e:
            warnings.warn(
                f"Failed to load calibrator {self.timeframe}: {e}. "
                "Using uncalibrated probabilities.",
                CalibrationWarning
            )
            self.is_fitted = False
            return False
    
    def _validate_calibrator(self):
        """
        Validate that the loaded calibrator works correctly.
        """
        try:
            # Test prediction
            test_probs = [0.3, 0.5, 0.7]
            results = self.isotonic.predict(test_probs)
            
            # Basic sanity checks
            if len(results) != 3:
                raise ValueError("Calibrator output length mismatch")
            
            if not all(0 <= r <= 1 for r in results):
                raise ValueError("Calibrator output out of bounds")
            
            return True
            
        except Exception as e:
            warnings.warn(
                f"Calibrator {self.timeframe} validation failed: {e}",
                CalibrationWarning
            )
            self.is_fitted = False
            return False
        
    def get_confidence_band(self, prob):
        """Return LOW / MEDIUM / HIGH based on probability strength"""
        # distance from 0.5
        dist = abs(prob - 0.5)
        if dist < 0.05:
            return "VERY_LOW"   # 0.45 - 0.55
        if dist < 0.10:
            return "LOW"        # 0.40 - 0.60
        if dist < 0.20:
            return "MEDIUM"     # 0.30 - 0.70
        if dist < 0.30:
            return "HIGH"       # 0.20 - 0.80
        return "VERY_HIGH"      # <0.20 or >0.80
    
    def get_stats(self):
        """Return calibration statistics for monitoring"""
        return {
            'timeframe': self.timeframe,
            'is_fitted': self.is_fitted,
            **self.calibration_stats
        }
