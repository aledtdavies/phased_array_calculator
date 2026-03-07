% Probe - Represents a phased array probe (linear or matrix).
classdef Probe
    properties
        NumElements     % Number of elements in the primary (X) axis
        Pitch           % Center-to-center distance in X axis (meters)
        Frequency       % Nominal frequency in Hz
        NumElementsY    % Number of elements in the passive (Y) axis
        PitchY          % Center-to-center distance in Y axis (meters)
    end
    
    methods
        function obj = Probe(numElements, pitch, frequency, numElementsY, pitchY)
            if nargin < 3
                frequency = 5e6;
            end
            if nargin < 4
                numElementsY = 1;
            end
            if nargin < 5
                pitchY = 0.0;
            end
            
            if numElementsY > 1 && pitchY <= 0
                error('PitchY must be > 0 when NumElementsY > 1');
            end
            
            obj.NumElements = numElements;
            obj.Pitch = pitch;
            obj.Frequency = frequency;
            obj.NumElementsY = max(1, numElementsY);
            obj.PitchY = pitchY;
        end
        
        function n = totalElements(obj)
            n = obj.NumElements * obj.NumElementsY;
        end
        
        function indices = getElementOfInterestIndices(obj)
            indices = 1:obj.totalElements();
        end
        
        function pos = getElementPositions(obj, centerAtOrigin)
            % Returns the (x, y, z) coordinates of the elements in the
            % PROBE's local coordinate system. Shape: (TotalElements, 3).
            if nargin < 2
                centerAtOrigin = true;
            end
            
            indicesX = 0:(obj.NumElements - 1);
            indicesY = 0:(obj.NumElementsY - 1);
            
            if centerAtOrigin
                totalWidthX = (obj.NumElements - 1) * obj.Pitch;
                xPos = indicesX * obj.Pitch - (totalWidthX / 2.0);
                
                totalWidthY = (obj.NumElementsY - 1) * obj.PitchY;
                yPos = indicesY * obj.PitchY - (totalWidthY / 2.0);
            else
                xPos = indicesX * obj.Pitch;
                yPos = indicesY * obj.PitchY;
            end
            
            % Create meshgrid (X varies fastest)
            [X, Y] = meshgrid(xPos, yPos);
            
            % Flatten (column-major, but transpose to match Python row-major ordering)
            xFlat = X(:);
            yFlat = Y(:);
            zFlat = zeros(size(xFlat));
            
            pos = [xFlat, yFlat, zFlat];
        end
    end
end
