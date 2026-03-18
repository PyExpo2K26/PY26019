# ═══════════════════════════════════════════════════════════════════════════
# FILE: utils/insurance_assessment.py
# Flood Insurance Risk & Damage Assessment
# ═══════════════════════════════════════════════════════════════════════════

from datetime import datetime


class InsuranceAssessor:
    """
    Estimates flood damage costs, insurance premiums, and generates
    property risk certificates for buildings in India.
    """

    # ── Construction cost per sq.m (INR) by building type ─────────────────
    REPLACEMENT_COSTS = {
        'residential_1story': 18_000,
        'residential_2story': 22_000,
        'commercial':         28_000,
        'industrial':         20_000,
    }

    # ── Depth-damage curves: flood depth (m) → damage fraction ────────────
    # Values are (depth_m, damage_fraction) pairs — linear interpolation used
    DEPTH_DAMAGE_CURVES = {
        'residential_1story': [
            (0.0, 0.00), (0.3, 0.08), (0.6, 0.18), (0.9, 0.30),
            (1.2, 0.42), (1.5, 0.55), (1.8, 0.65), (2.4, 0.78), (3.0, 0.90),
        ],
        'residential_2story': [
            (0.0, 0.00), (0.3, 0.05), (0.6, 0.12), (0.9, 0.20),
            (1.2, 0.30), (1.5, 0.40), (1.8, 0.50), (2.4, 0.62), (3.0, 0.75),
        ],
        'commercial': [
            (0.0, 0.00), (0.3, 0.10), (0.6, 0.22), (0.9, 0.35),
            (1.2, 0.48), (1.5, 0.60), (1.8, 0.70), (2.4, 0.82), (3.0, 0.92),
        ],
        'industrial': [
            (0.0, 0.00), (0.3, 0.06), (0.6, 0.14), (0.9, 0.24),
            (1.2, 0.35), (1.5, 0.46), (1.8, 0.57), (2.4, 0.70), (3.0, 0.85),
        ],
    }

    # ── Annual premium rates (% of replacement cost) by risk tier ─────────
    PREMIUM_RATES = {
        'Very Low':  0.25,
        'Low':       0.50,
        'Moderate':  1.00,
        'High':      1.75,
        'Very High': 2.75,
        'Extreme':   4.00,
    }

    # ──────────────────────────────────────────────────────────────────────
    def __init__(self):
        pass

    # ──────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _interpolate_damage(depth_m: float, curve: list) -> float:
        """Linear interpolation along a depth-damage curve."""
        if depth_m <= curve[0][0]:
            return curve[0][1]
        if depth_m >= curve[-1][0]:
            return curve[-1][1]
        for i in range(len(curve) - 1):
            d0, f0 = curve[i]
            d1, f1 = curve[i + 1]
            if d0 <= depth_m <= d1:
                t = (depth_m - d0) / (d1 - d0)
                return f0 + t * (f1 - f0)
        return curve[-1][1]

    @staticmethod
    def _risk_tier(damage_pct: float) -> str:
        if damage_pct < 5:
            return 'Very Low'
        if damage_pct < 15:
            return 'Low'
        if damage_pct < 30:
            return 'Moderate'
        if damage_pct < 50:
            return 'High'
        if damage_pct < 70:
            return 'Very High'
        return 'Extreme'

    @staticmethod
    def _insurability(damage_pct: float) -> str:
        if damage_pct < 20:
            return 'Standard cover available'
        if damage_pct < 50:
            return 'Cover available with conditions'
        if damage_pct < 75:
            return 'High-risk — limited cover, excess applies'
        return 'Uninsurable at standard terms — mitigation required'

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def estimate_building_damage(
        self,
        flood_depth_m: float,
        building_type: str,
        floor_area_sqm: float,
    ) -> dict:
        """
        Estimate flood damage and recommended annual premium.

        Args:
            flood_depth_m  : expected flood depth in metres
            building_type  : one of residential_1story / residential_2story /
                             commercial / industrial
            floor_area_sqm : gross floor area in square metres

        Returns:
            dict with keys:
              replacement_cost_inr, damage_fraction, damage_percent,
              damage_cost_inr, risk_tier, recommended_premium_pct,
              annual_premium_inr, insurability
        """
        btype = building_type if building_type in self.REPLACEMENT_COSTS else 'residential_1story'

        cost_per_sqm     = self.REPLACEMENT_COSTS[btype]
        replacement_cost = cost_per_sqm * floor_area_sqm

        curve            = self.DEPTH_DAMAGE_CURVES[btype]
        damage_fraction  = self._interpolate_damage(flood_depth_m, curve)
        damage_pct       = damage_fraction * 100
        damage_cost      = replacement_cost * damage_fraction

        risk_tier        = self._risk_tier(damage_pct)
        premium_pct      = self.PREMIUM_RATES[risk_tier]
        annual_premium   = replacement_cost * premium_pct / 100

        return {
            'replacement_cost_inr':    round(replacement_cost, 2),
            'damage_fraction':         round(damage_fraction, 4),
            'damage_percent':          round(damage_pct, 2),
            'damage_cost_inr':         round(damage_cost, 2),
            'risk_tier':               risk_tier,
            'recommended_premium_pct': round(premium_pct, 2),
            'annual_premium_inr':      round(annual_premium, 2),
            'insurability':            self._insurability(damage_pct),
        }

    # ──────────────────────────────────────────────────────────────────────

    def generate_property_certificate(
        self,
        property_address: str,
        flood_depth_m: float,
        building_type: str,
        floor_area_sqm: float,
        output_path: str = 'flood_risk_certificate.txt',
    ) -> str:
        """
        Generate a plain-text flood risk certificate and save to disk.

        Returns:
            path to the saved certificate file
        """
        assessment = self.estimate_building_damage(
            flood_depth_m  = flood_depth_m,
            building_type  = building_type,
            floor_area_sqm = floor_area_sqm,
        )

        lines = [
            "=" * 65,
            "       FLOOD RISK PROPERTY CERTIFICATE",
            "=" * 65,
            f"Issued:            {datetime.now().strftime('%d %B %Y, %H:%M')}",
            f"Valid Until:       {datetime.now().replace(year=datetime.now().year + 1).strftime('%d %B %Y')}",
            "",
            "PROPERTY DETAILS",
            "-" * 65,
            f"Address:           {property_address}",
            f"Building Type:     {building_type.replace('_', ' ').title()}",
            f"Floor Area:        {floor_area_sqm} sq.m",
            "",
            "FLOOD RISK ASSESSMENT",
            "-" * 65,
            f"Design Flood Depth:{flood_depth_m:.1f} m",
            f"Risk Tier:         {assessment['risk_tier']}",
            f"Damage Estimate:   {assessment['damage_percent']:.1f}% of replacement value",
            f"Insurability:      {assessment['insurability']}",
            "",
            "FINANCIAL SUMMARY (INR)",
            "-" * 65,
            f"Replacement Cost:  ₹{assessment['replacement_cost_inr']:>15,.0f}",
            f"Estimated Damage:  ₹{assessment['damage_cost_inr']:>15,.0f}",
            f"Annual Premium:    ₹{assessment['annual_premium_inr']:>15,.0f}"
            f"  ({assessment['recommended_premium_pct']:.2f}% of replacement)",
            "",
            "DISCLAIMER",
            "-" * 65,
            "This certificate is generated by an automated flood risk model",
            "for indicative purposes only. Figures are estimates based on",
            "depth-damage curves and do not constitute a formal insurance",
            "contract or valuation. Consult a licensed insurer for binding",
            "cover.",
            "=" * 65,
        ]

        content = "\n".join(lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path
