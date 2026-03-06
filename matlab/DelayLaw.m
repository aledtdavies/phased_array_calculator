classdef DelayLaw
    properties
        Probe
        Wedge
        Material
    end
    
    methods
        function obj = DelayLaw(probe, wedge, material)
            obj.Probe = probe;
            obj.Wedge = wedge;
            obj.Material = material;
        end
        
        function xInt = solveFermatPoint(obj, pStart, pEnd, v1, v2)
            x1 = pStart(1);
            z1 = pStart(2);
            x2 = pEnd(1);
            z2 = pEnd(2);
            
            H = x2 - x1;
            h1 = abs(z1);
            h2 = abs(z2);
            
            C = v2 / v1;
            C2 = C^2;
            
            a = 1.0 - C2;
            b = -2.0 * H * a;
            c = (H^2 + h1^2) - C2 * (H^2 + h2^2);
            d = -2.0 * H * (h1^2);
            e = (H^2) * (h1^2);
            
            r = roots([a, b, c, d, e]);
            
            % Filter valid roots
            isReal = abs(imag(r)) < 1e-9;
            realRoots = real(r(isReal));
            
            minTime = Inf;
            bestU = NaN;
            
            for k = 1:length(realRoots)
                u = realRoots(k);
                xCandidate = u + x1;
                
                dWedge = sqrt((xCandidate - x1)^2 + h1^2);
                dMat = sqrt((x2 - xCandidate)^2 + h2^2);
                
                t = dWedge / v1 + dMat / v2;
                
                if t < minTime
                    minTime = t;
                    bestU = u;
                end
            end
            
            if isnan(bestU)
                xInt = x1 + H * (h1 / (h1 + h2));
            else
                xInt = bestU + x1;
            end
        end
        
        function result = calculateLaw(obj, focalX, focalZ, waveType)
            if nargin < 4
                waveType = 'longitudinal';
            end
            
            elements = obj.Wedge.getTransformedElements(obj.Probe);
            numEls = obj.Probe.NumElements;
            
            tofs = zeros(numEls, 1);
            interfacePoints = zeros(numEls, 2);
            
            target = [focalX, focalZ];
            
            vWedge = obj.Wedge.Velocity;
            
            if strcmpi(waveType, 'shear') && ~isempty(obj.Material.VelocityShear)
                vMat = obj.Material.VelocityShear;
            else
                vMat = obj.Material.VelocityLongitudinal;
            end
            
            for i = 1:numEls
                pEl = elements(i, :);
                xInt = obj.solveFermatPoint(pEl, target, vWedge, vMat);
                pInt = [xInt, 0.0];
                
                interfacePoints(i, :) = pInt;
                
                distWedge = norm(pEl - pInt);
                distMat = norm(target - pInt);
                
                tofs(i) = distWedge / vWedge + distMat / vMat;
            end
            
            maxTof = max(tofs);
            delays = maxTof - tofs;
            
            result.Delays = delays;
            result.ToF = tofs;
            result.InterfacePoints = interfacePoints;
            result.FocalPoint = target;
            result.VelocityUsed = vMat;
        end
        
        function exportElementPositions(obj, filename)
            elements = obj.Wedge.getTransformedElements(obj.Probe);
            fprintf('Exporting elements to %s...\n', filename);
            
            coords_mm = elements * 1000.0;
            [~, ~, ext] = fileparts(filename);
            ext = lower(ext);
            
            if strcmp(ext, '.mat')
                ElementID = (1:obj.Probe.NumElements)';
                Global_X_mm = coords_mm(:, 1);
                Global_Z_mm = coords_mm(:, 2);
                Coordinates_mm = coords_mm;
                save(filename, 'ElementID', 'Global_X_mm', 'Global_Z_mm', 'Coordinates_mm');
            elseif strcmp(ext, '.m')
                fid = fopen(filename, 'w');
                fprintf(fid, '%% Element Positions (mm)\n');
                
                fprintf(fid, 'ElementID = [ %s ];\n', strjoin(arrayfun(@num2str, 1:obj.Probe.NumElements, 'UniformOutput', false), ', '));
                fprintf(fid, 'Global_X_mm = [ %s ];\n', strjoin(arrayfun(@num2str, coords_mm(:, 1)', 'UniformOutput', false), ', '));
                fprintf(fid, 'Global_Z_mm = [ %s ];\n', strjoin(arrayfun(@num2str, coords_mm(:, 2)', 'UniformOutput', false), ', '));
                
                fprintf(fid, 'Coordinates_mm = [\n');
                for i = 1:obj.Probe.NumElements
                    fprintf(fid, '    %.4f, %.4f;\n', coords_mm(i, 1), coords_mm(i, 2));
                end
                fprintf(fid, '];\n');
                fclose(fid);
            else
                fid = fopen(filename, 'w');
                fprintf(fid, 'ElementID,Global_X_mm,Global_Z_mm\n');
                for i = 1:obj.Probe.NumElements
                    x = coords_mm(i, 1);
                    z = coords_mm(i, 2);
                    fprintf(fid, '%d,%.4f,%.4f\n', i, x, z);
                end
                fclose(fid);
            end
        end
    end
end
