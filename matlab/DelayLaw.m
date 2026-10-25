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
            % 2D Fermat solver (quartic polynomial method).
            % pStart = [x, z], pEnd = [x, z]
            validateRay(pStart,pEnd,v1,v2);
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
        
        function [xi, yi] = solveFermatPoint3D(~, pStart, pEnd, v1, v2)
            % Planar isotropic ray in the vertical incidence plane.
            % Global metres, z<=0 incident side, z>0 component; speeds m/s.
            validateRay(pStart, pEnd, v1, v2);
            delta = pEnd(1:2)-pStart(1:2);
            distance = norm(delta);
            if distance == 0
                xi=pStart(1); yi=pStart(2); return;
            end
            L=max([distance,-pStart(3),pEnd(3)]);
            d=distance/L; h1=-pStart(3)/L; h2=pEnd(3)/L;
            ratio=v1/v2;
            residual=@(f) snellResidual(f,d,h1,h2,ratio);
            if h1==0 && residual(0)>=0
                fraction=0;
            else
                fraction=fzero(residual,[0,1],optimset('TolX',eps,'Display','off'));
                if abs(residual(fraction))>1e-10
                    error('DelayLaw:convergence','Snell solve did not satisfy its residual');
                end
            end
            point=pStart(1:2)+fraction*delta;
            xi=point(1); yi=point(2);
        end

        function result = calculateLaw(obj, focalX, focalY, focalZ, waveType)
            % Computes the delay law for a single focal point (3D).
            %
            % Args:
            %   focalX, focalY, focalZ: Target coordinates (meters)
            %   waveType: 'longitudinal' or 'shear'
            %
            % Returns struct with:
            %   Delays, ToF, InterfacePoints, FocalPoint, VelocityUsed
            
            if nargin < 3
                focalY = 0.0;
            end
            if nargin < 4
                focalZ = focalY;  % Legacy 2D call: calculateLaw(fx, fz)
                focalY = 0.0;
            end
            if nargin < 5
                waveType = 'longitudinal';
            end
            
            elements = obj.Wedge.getTransformedElements(obj.Probe);
            numEls = size(elements, 1);
            activeIndices = obj.Probe.getActiveElementIndices();
            
            tofs = nan(numEls, 1);
            interfacePoints = zeros(numEls, 3);
            
            target = [focalX, focalY, focalZ];
            
            vWedge = obj.Wedge.Velocity;
            
            if ~any(strcmpi(waveType,{'longitudinal','shear'}))
                error('DelayLaw:mode','waveType must be longitudinal or shear');
            end
            if strcmpi(waveType,'shear')
                if isempty(obj.Material.VelocityShear)
                    error('DelayLaw:mode','shear mode requires a shear wave speed');
                end
                vMat=obj.Material.VelocityShear;
            else
                vMat=obj.Material.VelocityLongitudinal;
            end
            validateRay(elements(1,:),target,vWedge,vMat);
            
            % Determine if 3D solver is needed
            hasY = any(abs(elements(:, 2)) > 1e-9) || abs(focalY) > 1e-9;
            
            for k = 1:length(activeIndices)
                i = activeIndices(k);
                pEl = elements(i, :);
                
                if hasY
                    % 3D solver
                    [xi, yi] = obj.solveFermatPoint3D(pEl, target, vWedge, vMat);
                    pInt = [xi, yi, 0.0];
                else
                    % 2D solver (faster, quartic)
                    pEl2D = [pEl(1), pEl(3)];
                    target2D = [focalX, focalZ];
                    xi = obj.solveFermatPoint(pEl2D, target2D, vWedge, vMat);
                    pInt = [xi, 0.0, 0.0];
                end
                
                interfacePoints(i, :) = pInt;
                
                distWedge = norm(pEl - pInt);
                distMat = norm(target - pInt);
                
                tofs(i) = distWedge / vWedge + distMat / vMat;
            end
            
            activeTofs = tofs(activeIndices);
            maxTof = max(activeTofs);
            
            delays = nan(numEls, 1);
            delays(activeIndices) = maxTof - tofs(activeIndices);
            
            result.Delays = delays;
            result.ToF = tofs;
            result.InterfacePoints = interfacePoints;
            result.FocalPoint = target;
            result.VelocityUsed = vMat;
            result.ActiveIndices = activeIndices;
        end
        
        function centre = apertureCentre(obj)
            % Centre of the active sub-aperture, global frame. Focal rules start the central ray here.
            elements = obj.Wedge.getTransformedElements(obj.Probe);
            centre = mean(elements(obj.Probe.getActiveElementIndices(), :), 1);
        end

        function exportElementPositions(obj, filename)
            elements = obj.Wedge.getTransformedElements(obj.Probe);
            fprintf('Exporting elements to %s...\n', filename);
            
            coords_mm = elements * 1000.0;
            numEls = size(elements, 1);
            [~, ~, ext] = fileparts(filename);
            ext = lower(ext);
            
            if strcmp(ext, '.mat')
                ElementID = (1:numEls)';
                Global_X_mm = coords_mm(:, 1);
                Global_Y_mm = coords_mm(:, 2);
                Global_Z_mm = coords_mm(:, 3);
                Coordinates_mm = coords_mm;
                save(filename, 'ElementID', 'Global_X_mm', 'Global_Y_mm', 'Global_Z_mm', 'Coordinates_mm');
            elseif strcmp(ext, '.m')
                fid = fopen(filename, 'w');
                fprintf(fid, '%% Element Positions (mm)\n');
                
                fprintf(fid, 'ElementID = [ %s ];\n', strjoin(arrayfun(@num2str, 1:numEls, 'UniformOutput', false), ', '));
                fprintf(fid, 'Global_X_mm = [ %s ];\n', strjoin(arrayfun(@num2str, coords_mm(:, 1)', 'UniformOutput', false), ', '));
                fprintf(fid, 'Global_Y_mm = [ %s ];\n', strjoin(arrayfun(@num2str, coords_mm(:, 2)', 'UniformOutput', false), ', '));
                fprintf(fid, 'Global_Z_mm = [ %s ];\n', strjoin(arrayfun(@num2str, coords_mm(:, 3)', 'UniformOutput', false), ', '));
                
                fprintf(fid, 'Coordinates_mm = [\n');
                for i = 1:numEls
                    fprintf(fid, '    %.4f, %.4f, %.4f;\n', coords_mm(i, 1), coords_mm(i, 2), coords_mm(i, 3));
                end
                fprintf(fid, '];\n');
                fclose(fid);
            else
                fid = fopen(filename, 'w');
                fprintf(fid, 'ElementID,Global_X_mm,Global_Y_mm,Global_Z_mm\n');
                for i = 1:numEls
                    fprintf(fid, '%d,%.4f,%.4f,%.4f\n', i, coords_mm(i, 1), coords_mm(i, 2), coords_mm(i, 3));
                end
                fclose(fid);
            end
        end
    end
end

function validateRay(a,b,c1,c2)
    if numel(a)~=numel(b) || ~ismember(numel(a),[2,3]) || ...
            any(~isfinite(a)) || any(~isfinite(b)) || ...
            ~isscalar(c1) || ~isscalar(c2) || ~isfinite(c1) || ~isfinite(c2) || c1<=0 || c2<=0 || ...
            a(end)>0 || b(end)<=0
        error('DelayLaw:domain','Finite ray endpoints require source z<=0, focus z>0 and positive speeds');
    end
end

function value=snellResidual(f,d,h1,h2,ratio)
    u=d*f; remaining=d*(1-f);
    if h1==0 && f==0
        incident=1;
    else
        incident=u/hypot(u,h1);
    end
    value=incident-ratio*remaining/hypot(remaining,h2);
end
