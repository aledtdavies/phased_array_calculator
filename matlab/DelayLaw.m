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
            fid = fopen(filename, 'w');
            fprintf(fid, 'ElementID,Global_X_mm,Global_Z_mm\n');
            for i = 1:obj.Probe.NumElements
                x = elements(i, 1);
                z = elements(i, 2);
                fprintf(fid, '%d,%.4f,%.4f\n', i, x * 1000, z * 1000);
            end
            fclose(fid);
        end
    end
end
