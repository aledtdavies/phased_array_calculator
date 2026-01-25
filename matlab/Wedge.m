classdef Wedge properties AngleDegrees HeightAtElement1 Velocity ProbeOffsetX
    end methods function obj = Wedge(angle, heightAtEl1, velocity, probeOffset)
                                   obj.AngleDegrees = angle;
obj.HeightAtElement1 = heightAtEl1;
obj.Velocity = velocity;
if nargin
  > 3 obj.ProbeOffsetX = probeOffset;
else
  obj.ProbeOffsetX = 0;
end end function globalPoints = getTransformedElements(obj, probe) localCoords =
    probe.getElementPositions(false);
localX = localCoords( :, 1);
localZ = localCoords( :, 2);
angleRad = deg2rad(obj.AngleDegrees);
c = cos(angleRad);
s = sin(angleRad);
rotX = localX.*c - localZ.*s;
rotZ = -localX.*s - localZ.*c;
globalX = rotX + obj.ProbeOffsetX;
globalZ = rotZ - obj.HeightAtElement1;
globalPoints = [ globalX, globalZ ];
end end end
