% Probe - Represents a linear phased array probe.
classdef Probe
    properties
        NumElements % Number of elements
        Pitch       % Center-to-center distance between elements in meters
        Frequency   % Nominal frequency in Hz
    end
    
    methods
        function obj = Probe(numElements, pitch, frequency)
            % Probe Constructor
            if nargin < 3
                frequency = 5e6;
            end
            obj.NumElements = numElements;
            obj.Pitch = pitch;
            obj.Frequency = frequency;
        end
        
        function indices = getElementOfInterestIndices(obj)
            indices = 1:obj.NumElements;
        end
        
        function pos = getElementPositions(obj, centerAtOrigin)
            % Returns the (x, z) coordinates of the elements in the PROBE's local coordinate system.
            % The array line is along the x-axis, z is 0.
            if nargin < 2
                centerAtOrigin = true;
            end
            
            indices = 0:(obj.NumElements - 1);
            
            if centerAtOrigin
                totalWidth = (obj.NumElements - 1) * obj.Pitch;
                xPositions = (indices * obj.Pitch) - (totalWidth / 2.0);
            else
                xPositions = indices * obj.Pitch;
            end
            
            zPositions = zeros(size(xPositions));
            pos = [xPositions(:), zPositions(:)];
        end
    end
end
