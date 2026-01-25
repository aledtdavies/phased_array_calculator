classdef Material properties VelocityLongitudinal VelocityShear end methods
    function obj = Material(vel_l, vel_s) obj.VelocityLongitudinal = vel_l;
if nargin
  > 1 obj.VelocityShear = vel_s;
else
  obj.VelocityShear = [];
end end end end
