% Wedge - Represents the wedge (prism) between the probe and the component.
% Handles coordinate transformation from Probe Frame to Global Frame.
%
% Global Frame Convention:
%   Interface plane: Z = 0
%   Component: Z > 0
%   Wedge: Z < 0
classdef Wedge
    properties
        AngleDegrees        % Wedge angle (pitch around Y axis)
        AngleRad            % Wedge angle in radians
        HeightAtElement1    % Vertical distance from Element 1 to Interface (z=0)
        Velocity            % Longitudinal velocity of sound in wedge (m/s)
        ProbeOffsetX        % Global X position of Element 1
        RoofAngleDegrees    % Roof angle (roll around X axis) for dual probes
        RoofAngleRad        % Roof angle in radians
    end
    
    methods
        function obj = Wedge(angleDegrees, heightAtElement1, velocity, probeOffsetX, roofAngleDegrees)
            if nargin < 4
                probeOffsetX = 0.0;
            end
            if nargin < 5
                roofAngleDegrees = 0.0;
            end
            obj.AngleDegrees = angleDegrees;
            obj.AngleRad = deg2rad(angleDegrees);
            obj.HeightAtElement1 = heightAtElement1;
            obj.Velocity = velocity;
            obj.ProbeOffsetX = probeOffsetX;
            obj.RoofAngleDegrees = roofAngleDegrees;
            obj.RoofAngleRad = deg2rad(roofAngleDegrees);
        end
        
        function globalCoords = getTransformedElements(obj, probe)
            % Computes the GLOBAL (x, y, z) coordinates of the probe elements.
            %
            % Steps:
            %   1. Get local probe coords (first element at 0,0,0)
            %   2. Rotate by wedge angle (Y-axis pitch)
            %   3. Rotate by roof angle (X-axis roll)
            %   4. Translate to global position
            
            % 1. Get local probe coordinates
            localCoords = probe.getElementPositions(false);
            localX = localCoords(:, 1);
            localY = localCoords(:, 2);
            localZ = localCoords(:, 3);
            
            % 2. Rotate around Y axis (Pitch)
            c1 = cos(obj.AngleRad);
            s1 = sin(obj.AngleRad);
            
            rotX1 = localX .* c1 - localZ .* s1;
            rotY1 = localY;
            rotZ1 = -localX .* s1 - localZ .* c1;
            
            % 3. Rotate around X axis (Roof/Roll)
            if isa(probe, 'DualProbe')
                % For dual probes, enforce symmetric roof: TX = -roof, RX = +roof.
                nHalf = probe.totalElements() / 2;
                roofAngles = [-obj.RoofAngleRad * ones(nHalf, 1); obj.RoofAngleRad * ones(nHalf, 1)];
                c2 = cos(roofAngles);
                s2 = sin(roofAngles);
            else
                c2 = cos(obj.RoofAngleRad);
                s2 = sin(obj.RoofAngleRad);
            end
            
            rotX2 = rotX1;
            rotY2 = rotY1 .* c2 - rotZ1 .* s2;
            rotZ2 = rotY1 .* s2 + rotZ1 .* c2;
            
            % 4. Translate
            globalX = rotX2 + obj.ProbeOffsetX;
            globalY = rotY2;
            globalZ = rotZ2 - obj.HeightAtElement1;
            
            globalCoords = [globalX, globalY, globalZ];
        end
    end
end
