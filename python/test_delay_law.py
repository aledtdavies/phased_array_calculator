"""Analytic invariants and regression cases from the 2D/3D delay review."""
import math
import unittest
import numpy as np
from delay_law import DelayLaw
from material import Material
from probe import Probe
from wedge import Wedge


class TestDelayLaw(unittest.TestCase):
    def solver(self, matrix=False):
        p=Probe(8,.0006,num_elements_y=4 if matrix else 1,pitch_y=.0006)
        return DelayLaw(p,Wedge(20,.01,1480),Material(5900,3240))

    def test_3d_incidence_plane_matches_independent_quartic(self):
        s=self.solver(True)
        rng=np.random.default_rng(20261022)
        for c1,c2 in [(1480,5900),(2330,3240),(5900,2330),(5900,5900)]:
            for _ in range(40):
                a=np.array([.002,-.003,-10**rng.uniform(-4,-1)])
                b=np.r_[rng.uniform(-.15,.15,2),10**rng.uniform(-3,-1)]
                delta=b[:2]-a[:2]; distance=np.linalg.norm(delta)
                u=s.solve_fermat_point([0,a[2]],[distance,b[2]],c1,c2)
                expected=a[:2]+u/distance*delta
                np.testing.assert_allclose(s.solve_fermat_point_3d(a,b,c1,c2),expected,atol=2e-11,rtol=0)

    def test_known_snell_angles(self):
        s=self.solver()
        a=math.radians(12); b=math.asin(5900/1480*math.sin(a))
        horizontal=.01*math.tan(a)+.02*math.tan(b)
        for direction in [np.array([1.,0]),np.array([.6,.8]),np.array([-.6,-.8])]:
            target=np.r_[horizontal*direction,.02]
            expected=.01*math.tan(a)*direction
            np.testing.assert_allclose(s.solve_fermat_point_3d([0,0,-.01],target,1480,5900),expected,atol=1e-14,rtol=0)

    def test_stress_ray_residual(self):
        s=self.solver(); a=np.array([0,0,-.002044892795101922]); b=np.array([-.12862425783529333,0,.001223327348617447])
        q=np.r_[s.solve_fermat_point_3d(a,b,1480,5900),0]
        residual=(q[:2]-a[:2])/(1480*np.linalg.norm(q-a))+(q[:2]-b[:2])/(5900*np.linalg.norm(q-b))
        self.assertLess(np.linalg.norm(residual),1e-12)

    def test_equal_speed_3d_is_straight_segment(self):
        s=self.solver(); a=np.array([.02,-.01,-.01]); b=np.array([-.03,.02,.04])
        np.testing.assert_allclose(s.solve_fermat_point_3d(a,b,5900,5900),(a+.2*(b-a))[:2],atol=1e-14)

    def test_mutable_geometry_and_aperture_invalidate_cache(self):
        s=self.solver(); s.calculate_law(.03,0,.04)
        s.probe.start_element=4; s.probe.num_active_elements=2; s.wedge.probe_offset_x=.007
        actual=s.calculate_law(.03,0,.04)
        fresh=DelayLaw(s.probe,s.wedge,s.material).calculate_law(.03,0,.04)
        np.testing.assert_array_equal(np.flatnonzero(np.isfinite(actual['delays'])),[3,4])
        np.testing.assert_array_equal(actual['delays'],fresh['delays'])
        actual['active_indices'][0]=0
        np.testing.assert_array_equal(s.calculate_law(.03,0,.04)['active_indices'],[3,4])

    def test_repeated_laws_reuse_geometry(self):
        s=self.solver(); original=s.wedge.get_transformed_elements; calls=[]
        def counted(p):
            calls.append(1)
            return original(p)
        s.wedge.get_transformed_elements=counted
        s.calculate_law(.03,0,.04); s.calculate_law(.04,0,.04)
        self.assertEqual(len(calls),1)

    def test_unknown_mode_and_missing_shear_are_refused(self):
        s=self.solver()
        with self.assertRaises(ValueError): s.calculate_law(.03,0,.04,wave_type='banana')
        s.material=Material(5900)
        with self.assertRaises(ValueError): s.calculate_law(.03,0,.04,wave_type='shear')

    def test_invalid_geometry_and_speeds_are_refused(self):
        s=self.solver()
        for target in [[.03,0,-.04],[np.nan,0,.04],[.03,0,0]]:
            with self.assertRaises(ValueError): s.calculate_law(*target)
        for speed in [0,-1,np.nan,np.inf]:
            with self.assertRaises(ValueError): s.solve_fermat_point_3d([0,0,-.01],[.03,.02,.04],speed,5900)

    def test_contact_equal_speed(self):
        s=self.solver()
        np.testing.assert_array_equal(s.solve_fermat_point_3d([.01,.02,0],[.03,.04,.05],5900,5900),[.01,.02])

    def test_gui_skew_rotates_both_legs_of_the_centre_ray(self):
        from app import (_compute_base_focal, _compute_skewed_focal_point,
                         FOCUS_CONSTANT_DEPTH, Y_MODE_DERIVED_FROM_SKEW)
        beta=math.radians(45); skew=math.radians(30)
        entry=.01*math.tan(math.asin(1480/5900*math.sin(beta)))
        z,primary,fx=_compute_base_focal(FOCUS_CONSTANT_DEPTH,.01,beta,entry)
        x,ys,z=_compute_skewed_focal_point(FOCUS_CONSTANT_DEPTH,skew,entry,fx,beta,z,primary,
                                          0,None,Y_MODE_DERIVED_FROM_SKEW,entry_offset=entry)
        target=np.array([x,ys[0],z])
        q=np.r_[self.solver().solve_fermat_point_3d([0,0,-.01],target,1480,5900),0]
        direction=target-q
        self.assertAlmostEqual(math.atan2(np.linalg.norm(direction[:2]),direction[2]),beta,places=12)
        self.assertAlmostEqual(math.atan2(direction[1],direction[0]),skew,places=12)


if __name__=='__main__': unittest.main()
