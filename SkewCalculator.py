from UM.Logger import Logger
from .PluginConstants import PluginConstants
import math

class SkewCalculator:
    """
    Calculates skew factors and generates G-code commands based on measured distances
    from a calibration print.

    The calculator takes nine measurements corresponding to diagonals and sides of
    three orthogonal planes (XY, XZ, YZ) of a calibration object.
    It then computes skew factors for each plane and can generate
    Marlin (M852) and Klipper (SET_SKEW) G-code commands.
    """
    def __init__(self) -> None:
        """
        Initializes the SkewCalculator with default measurement values (typically representing an ideal print).
        """
        self.xy_ac = 141.42
        self.xy_bd = 141.42
        self.xy_ad = 100.0
        self.xz_ac = 141.42
        self.xz_bd = 141.42
        self.xz_ad = 100.0
        self.yz_ac = 141.42
        self.yz_bd = 141.42
        self.yz_ad = 100.0
        self.marlin_I = 0.0
        self.marlin_J = 0.0
        self.marlin_K = 0.0
        self.calculate_skew_factors() # Initial calculation

    def set_measurements(
        self,
        xy_ac: float, xy_bd: float, xy_ad: float,
        xz_ac: float, xz_bd: float, xz_ad: float,
        yz_ac: float, yz_bd: float, yz_ad: float
    ) -> None:
        """
        Sets the measured distances for all three planes.

        Args:
            xy_ac (float): Measured distance AC in the XY plane.
            xy_bd (float): Measured distance BD in the XY plane.
            xy_ad (float): Measured distance AD (side length) in the XY plane.
            xz_ac (float): Measured distance AC in the XZ plane.
            xz_bd (float): Measured distance BD in the XZ plane.
            xz_ad (float): Measured distance AD (side length) in the XZ plane.
            yz_ac (float): Measured distance AC in the YZ plane.
            yz_bd (float): Measured distance BD in the YZ plane.
            yz_ad (float): Measured distance AD (side length) in the YZ plane.
        """
        self.xy_ac = xy_ac
        self.xy_bd = xy_bd
        self.xy_ad = xy_ad
        self.xz_ac = xz_ac
        self.xz_bd = xz_bd
        self.xz_ad = xz_ad
        self.yz_ac = yz_ac
        self.yz_bd = yz_bd
        self.yz_ad = yz_ad
        self.calculate_skew_factors()

    def calculate_skew_factors(self):
        """
        Calculates the skew factors for all three planes (XY, XZ, YZ)
        using the current measurement values.
        """
        try:
            AC = float(self.xy_ac)
            BD = float(self.xy_bd)
            AD = float(self.xy_ad)
            if AD <= 0: raise ValueError("AD distance must be positive")
            self.marlin_I = (AC**2 - BD**2) / (4 * AD**2)
        except (ValueError, TypeError, ZeroDivisionError) as e:
            Logger.log("w", f"Could not calculate Marlin I factor (XY): {e}. Using 0.0")
            self.marlin_I = 0.0

        try:
            AC = float(self.xz_ac)
            BD = float(self.xz_bd)
            AD = float(self.xz_ad)
            if AD <= 0: raise ValueError("AD distance must be positive")
            self.marlin_J = (AC**2 - BD**2) / (4 * AD**2) if AD != 0 else 0.0
        except (ValueError, TypeError, ZeroDivisionError) as e:
            Logger.log("w", f"Could not calculate Marlin J factor (XZ): {e}. Using 0.0")
            self.marlin_J = 0.0

        try:
            AC = float(self.yz_ac)
            BD = float(self.yz_bd)
            AD = float(self.yz_ad)
            if AD <= 0: raise ValueError("AD distance must be positive")
            self.marlin_K = (AC**2 - BD**2) / (4 * AD**2) if AD != 0 else 0.0
        except (ValueError, TypeError, ZeroDivisionError) as e:
            Logger.log("w", f"Could not calculate Marlin K factor (YZ): {e}. Using 0.0")
            self.marlin_K = 0.0

        Logger.log("i", f"Calculated Marlin Factors: I={self.marlin_I:.8f}, J={self.marlin_J:.8f}, K={self.marlin_K:.8f}")

    def _calculate_skew_factor(self, ac: float, bd: float, ad: float) -> float:
        """
        Calculates the skew factor for a single plane given its measurements.

        The formula is derived from the geometry of a skewed square/rectangle.
        If ad (side length) is zero or measurements lead to a domain error for acos,
        it returns 0.0 to prevent math errors.

        Args:
            ac (float): Measured length of diagonal AC.
            bd (float): Measured length of diagonal BD.
            ad (float): Measured length of side AD (used as the reference side).

        Returns:
            float: The calculated skew factor, or 0.0 if inputs are invalid.
        """
        try:
            if ad == 0:
                return 0.0
            skew_factor = (ac**2 - bd**2) / (2 * ad**2)
            # Clamp value to prevent math domain error in acos
            skew_factor = max(-1.0, min(1.0, skew_factor))
            return math.acos(skew_factor) / math.pi * 180.0
        except (ValueError, TypeError):
            return 0.0

    def get_skew_factors(self) -> tuple[float, float, float]:
        """
        Calculates and returns the skew factors for XY, XZ, and YZ planes.

        Returns:
            tuple[float, float, float]: A tuple containing the skew factors for
                                        (XY_skew_factor, XZ_skew_factor, YZ_skew_factor).
        """
        return self.marlin_I, self.marlin_J, self.marlin_K

    def get_marlin_command(self) -> str:
        """
        Generates the Marlin M852 G-code command based on the calculated skew factors.

        Returns:
            str: The M852 command string (e.g., "M852 I0.00 J0.00 K0.00 ; PrintSkewCompensation").
                 Returns an error message if factors could not be calculated.
        """
        return f"M852 I{self.marlin_I:.8f} J{self.marlin_J:.8f} K{self.marlin_K:.8f} ; {PluginConstants.PLUGIN_ID}"

    def get_klipper_command(self) -> str:
        """
        Generates the Klipper SET_SKEW G-code command using the raw measurements.

        Note: Klipper's SET_SKEW command typically uses the direct measurements
        of the calibration object rather than pre-calculated skew factors.

        Returns:
            str: The SET_SKEW command string (e.g., "SET_SKEW XY=141.42,141.42,100.00 XZ=... YZ=... ; PrintSkewCompensation").
                 Returns an error message if measurement data is invalid or missing.
        """
        try:
            xy_part = f"XY={float(self.xy_ac):.3f},{float(self.xy_bd):.3f},{float(self.xy_ad):.3f}"
            xz_part = f"XZ={float(self.xz_ac):.3f},{float(self.xz_bd):.3f},{float(self.xz_ad):.3f}"
            yz_part = f"YZ={float(self.yz_ac):.3f},{float(self.yz_bd):.3f},{float(self.yz_ad):.3f}"
            return f"SET_SKEW {xy_part} {xz_part} {yz_part} ; {PluginConstants.PLUGIN_ID}"
        except (ValueError, TypeError) as e:
            Logger.log("w", f"Could not format Klipper command due to invalid measurement type: {e}")
            return f"SET_SKEW ; Error: Invalid measurements ({PluginConstants.PLUGIN_ID})"
