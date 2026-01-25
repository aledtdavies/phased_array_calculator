classdef Probe
    properties
        NumElements
        Pitch
        Frequency
    end
    
    methods
        function obj = Probe(num_elements, pitch, frequency)
            obj.NumElements = num_elements;
            obj.Pitch = pitch;
            if nargin > 2
                obj.Frequency = frequency;
            else
                obj.Frequency = 5e6;
            end
        end
        
        function positions = getElementPositions(obj, centerAtOrigin)
            if nargin < 2
                centerAtOrigin = true;
            end
            
            indices = 0:(obj.NumElements - 1);
            
            if centerAtOrigin
                totalWidth = (obj.NumElements - 1) * obj.Pitch;
                xPos = indices * obj.Pitch - (totalWidth / 2.0);
            else
                xPos = indices * obj.Pitch;
            end
            
            zPos = zeros(size(xPos));
            
            positions = [xPos', zPos']; % Nx2 matrix returned
        end
    end
end
