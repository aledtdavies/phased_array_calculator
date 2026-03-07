% DualProbe - Represents a dual phased array probe (two identical sub-arrays).
classdef DualProbe < Probe
    properties
        ArraySeparation % Distance between sub-array centres in Y (meters)
    end
    
    methods
        function obj = DualProbe(numElements, pitch, frequency, numElementsY, pitchY, arraySeparation)
            if nargin < 3
                frequency = 5e6;
            end
            if nargin < 4
                numElementsY = 1;
            end
            if nargin < 5
                pitchY = 0.0;
            end
            if nargin < 6
                arraySeparation = 0.0;
            end
            
            obj = obj@Probe(numElements, pitch, frequency, numElementsY, pitchY);
            obj.ArraySeparation = arraySeparation;
        end
        
        function n = totalElements(obj)
            n = 2 * totalElements@Probe(obj);
        end
        
        function pos = getElementPositions(obj, centerAtOrigin)
            % Returns (2N, 3) coordinates — two sub-arrays offset in Y.
            if nargin < 2
                centerAtOrigin = true;
            end
            
            baseCoords = getElementPositions@Probe(obj, centerAtOrigin);
            
            % Sub-array 1: offset -sep/2 in Y
            coords1 = baseCoords;
            coords1(:, 2) = coords1(:, 2) - obj.ArraySeparation / 2.0;
            
            % Sub-array 2: offset +sep/2 in Y
            coords2 = baseCoords;
            coords2(:, 2) = coords2(:, 2) + obj.ArraySeparation / 2.0;
            
            pos = [coords1; coords2];
        end
    end
end
