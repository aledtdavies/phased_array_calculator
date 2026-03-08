% Probe - Represents a phased array probe (linear or matrix).
classdef Probe
    properties
        NumElements     % Number of elements in the primary (X) axis
        Pitch           % Center-to-center distance in X axis (meters)
        Frequency       % Nominal frequency in Hz
        NumElementsY    % Number of elements in the passive (Y) axis
        PitchY          % Center-to-center distance in Y axis (meters)
        StartElement    % First active element (1-indexed)
        NumActiveElements % Number of active elements (0 = all)
        ElementOrder    % 'column-first' or 'row-first'
    end
    
    methods
        function obj = Probe(numElements, pitch, frequency, numElementsY, pitchY, startEl, numActive, elOrder)
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
                startEl = 1;
            end
            if nargin < 7
                numActive = 0;
            end
            if nargin < 8
                elOrder = 'column-first';
            end
            
            if numElementsY > 1 && pitchY <= 0
                error('PitchY must be > 0 when NumElementsY > 1');
            end
            
            obj.NumElements = numElements;
            obj.Pitch = pitch;
            obj.Frequency = frequency;
            obj.NumElementsY = max(1, numElementsY);
            obj.PitchY = pitchY;
            obj.StartElement = max(1, startEl);
            obj.NumActiveElements = max(0, numActive);
            obj.ElementOrder = elOrder;
        end
        
        function n = totalElements(obj)
            n = obj.NumElements * obj.NumElementsY;
        end
        
        function indices = getElementOfInterestIndices(obj)
            indices = obj.getActiveElementIndices();
        end
        
        function indices = getActiveElementIndices(obj)
            % Returns 1-based indices of active elements in the sub-aperture
            total = obj.totalElements();
            if obj.NumActiveElements > 0
                numActive = obj.NumActiveElements;
            else
                numActive = total;
            end
            
            startIdx = max(1, min(obj.StartElement, total));
            endIdx = min(startIdx + numActive - 1, total);
            
            userIndices = startIdx:endIdx;
            
            if strcmp(obj.ElementOrder, 'row-first') && obj.NumElementsY > 1
                Nx = obj.NumElements;
                Ny = obj.NumElementsY;
                % User numbering (1-based, row-first): iy = ceil(idx/Nx), ix = mod(idx-1, Nx)+1
                % Internal (column-first): internal = (ix-1)*Ny + iy
                userIdx0 = userIndices - 1;  % 0-based
                iy = floor(userIdx0 / Nx);   % 0-based row
                ix = mod(userIdx0, Nx);      % 0-based col
                internalIdx0 = ix * Ny + iy; % 0-based internal
                indices = sort(internalIdx0 + 1); % back to 1-based
            else
                indices = userIndices;
            end
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
