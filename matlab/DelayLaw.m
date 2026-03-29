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
            % 3D Fermat solver using Newton-Raphson with analytical Hessian.
            %
            % Finds the point P(xi, yi, 0) on the interface that minimises
            % travel time from pStart(x1, y1, z1) to pEnd(x2, y2, z2).
            %
            % Falls back to fminsearch if NR fails to converge.
            
            x1 = pStart(1); y1 = pStart(2); z1 = pStart(3);
            x2 = pEnd(1);   y2 = pEnd(2);   z2 = pEnd(3);
            
            % Guard for degenerate geometry
            if norm([x1 - x2, y1 - y2]) < 1e-9
                xi = x1;
                yi = y1;
                return;
            end
            
            % Initial guess via linear interpolation
            h1 = abs(z1);
            h2 = abs(z2);
            denom = h1 + h2;
            if denom > 0
                ratio = h1 / denom;
            else
                ratio = 0.5;
            end
            
            u = [x1 + (x2 - x1) * ratio; ...
                 y1 + (y2 - y1) * ratio];
            
            maxIter = 20;
            tol = 1e-12;
            
            for iter = 1:maxIter
                % Gradient
                dx1 = u(1) - x1;  dy1 = u(2) - y1;
                dx2 = x2 - u(1);  dy2 = y2 - u(2);
                d1 = sqrt(dx1^2 + dy1^2 + z1^2);
                d2 = sqrt(dx2^2 + dy2^2 + z2^2);
                
                gx = dx1 / (v1 * d1) - dx2 / (v2 * d2);
                gy = dy1 / (v1 * d1) - dy2 / (v2 * d2);
                g = [gx; gy];
                
                if norm(g) < tol
                    xi = u(1);
                    yi = u(2);
                    return;
                end
                
                % Hessian (with epsilon guard)
                eps_guard = 1e-12;
                d1_2 = dx1^2 + dy1^2 + z1^2 + eps_guard;
                d2_2 = dx2^2 + dy2^2 + z2^2 + eps_guard;
                d1_3 = d1_2 * sqrt(d1_2);
                d2_3 = d2_2 * sqrt(d2_2);
                
                hxx = (d1_2 - dx1^2) / (v1 * d1_3) + (d2_2 - dx2^2) / (v2 * d2_3);
                hyy = (d1_2 - dy1^2) / (v1 * d1_3) + (d2_2 - dy2^2) / (v2 * d2_3);
                hxy = -dx1 * dy1 / (v1 * d1_3) - dx2 * dy2 / (v2 * d2_3);
                
                % Explicit determinant and inversion (Cramer's rule for 2x2)
                detH = hxx * hyy - hxy^2;
                
                % Check for singularity (equivalent to rcond(H) check)
                if abs(detH) < 1e-25
                    break; % Singular Hessian — fall through to fminsearch
                end
                
                du_x = (-g(1) * hyy + g(2) * hxy) / detH;
                du_y = (-g(2) * hxx + g(1) * hxy) / detH;

                u = u + [du_x; du_y];
            end
            
            % Fallback to fminsearch if NR did not converge
            timeFun = @(uv) sqrt((uv(1) - x1)^2 + (uv(2) - y1)^2 + z1^2) / v1 + ...
                           sqrt((x2 - uv(1))^2 + (y2 - uv(2))^2 + z2^2) / v2;
            
            opts = optimset('Display', 'off', 'TolX', 1e-12, 'TolFun', 1e-12);
            uOpt = fminsearch(timeFun, u, opts);
            xi = uOpt(1);
            yi = uOpt(2);
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
                focalZ = focalX;  % Legacy 2D call: calculateLaw(fx, fz)
                focalX = focalY;  % Shift arguments
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
            
            if strcmpi(waveType, 'shear') && ~isempty(obj.Material.VelocityShear)
                vMat = obj.Material.VelocityShear;
            else
                vMat = obj.Material.VelocityLongitudinal;
            end
            
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
