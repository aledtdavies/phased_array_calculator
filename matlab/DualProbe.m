% DualProbe - Represents a dual phased array probe (two identical sub-arrays).
classdef DualProbe < Probe
    properties
        ArraySeparation % Distance between sub-array centres in Y (meters)
    end
    
    methods
        function obj = DualProbe(numElements, pitch, frequency, numElementsY, pitchY, arraySeparation, startEl, numActive, elOrder)
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
            if nargin < 7
                startEl = 1;
            end
            if nargin < 8
                numActive = 0;
            end
            if nargin < 9
                elOrder = 'column-first';
            end
            
            obj = obj@Probe(numElements, pitch, frequency, numElementsY, pitchY, startEl, numActive, elOrder);
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

            if ~centerAtOrigin
                % Keep dual-array separation symmetric about y=0 even when
                % element-1 anchoring is used for X/Z transformations.
                baseCoords(:, 2) = baseCoords(:, 2) - mean(baseCoords(:, 2));
            end
            
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
