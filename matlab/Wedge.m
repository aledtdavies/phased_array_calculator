% Wedge - Represents the wedge (prism) between the probe and the component.
classdef Wedge
    properties
        AngleDegrees    % Wedge angle
        AngleRad        % Wedge angle in radians
        HeightAtElement1% Vertical distance from Element 1 center to the Interface (z=0)
        Velocity        % Longitudinal Velocity of sound in the wedge material (m/s)
        ProbeOffsetX    % global X position of Element 1
    end
    
    methods
        function obj = Wedge(angleDegrees, heightAtElement1, velocity, probeOffsetX)
            % Wedge Constructor
            if nargin < 4
                probeOffsetX = 0.0;
            end
            obj.AngleDegrees = angleDegrees;
            obj.AngleRad = deg2rad(angleDegrees);
            obj.HeightAtElement1 = heightAtElement1;
            obj.Velocity = velocity;
            obj.ProbeOffsetX = probeOffsetX;
        end
        
        function globalCoords = getTransformedElements(obj, probe)
            % Computes the GLOBAL (x, z) coordinates of the probe elements.
            
            % 1. Get local probe coordinates (First element at 0,0)
            localCoords = probe.getElementPositions(false);
            localX = localCoords(:, 1);
            localZ = localCoords(:, 2);
            
            % 2. Rotate
            c = cos(obj.AngleRad);
            s = sin(obj.AngleRad);
            
            rotX = localX .* c - localZ .* s;
            rotZ = -localX .* s - localZ .* c;
            
            % 3. Translate
            globalX = rotX + obj.ProbeOffsetX;
            globalZ = rotZ - obj.HeightAtElement1;
            
            globalCoords = [globalX, globalZ];
        end
    end
end
