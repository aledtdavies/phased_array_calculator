classdef FocalRules
    %FOCALRULES Focal-target rules: where each law of an angle (and skew) sweep is focused.
    %
    %   T = FocalRules.targets(solver, mode, value, anglesDeg, skewsDeg, wave, yMode, yValues)
    %
    %   The MATLAB twin of python/focal_rules.py; tests/focal_rule_cases.json holds shared cases
    %   both editions are checked against (testFocalRules.m, test_focal_rules.py).
    %
    %   Frame (SI): X along the wedge, Y across, Z down into the component, Z = 0 the
    %   interface. Refracted angle beta from +Z towards the facing direction (+X at zero
    %   skew); skew about +Z from +X towards +Y. Beam direction (sin b cos s, sin b sin s,
    %   cos b). The central ray starts at the active sub-aperture's centre, crosses the wedge
    %   at alpha (sin alpha = vWedge / vComponent * sin beta) and enters the component
    %   h * tan(alpha) from the centre along the skew direction; both legs rotate with skew.
    %
    %   mode   'constant-depth' (Z = value), 'vertical-line' (X = value) or 'sound-path'
    %          (distance value along the central ray from its entry point); metres
    %   wave   'longitudinal' or 'shear'
    %   yMode  'from-skew' (default), 'fixed' (Y = yValues, one value; not with sound-path)
    %          or 'sweep' (one law per Y; in sound-path mode the skew is solved per Y and
    %          the skew list is used once)
    %
    %   T: struct array in sweep order (angle, skew, Y) with fields Angle, Skew (deg; NaN
    %   when not applicable), X, Y, Z (m; NaN when refused) and Reason ('' for a target, else
    %   'critical angle', 'focus not below surface', 'beam parallel to line' or
    %   'Y out of reach'). Invalid arguments raise errors (FocalRules:input).

    properties (Constant)
        ParallelTol = 1e-9
        ZeroReach = 1e-12   % m: horizontal reach treated as none (sound-path Y sweep)
    end

    methods (Static)
        function T = targets(solver, mode, value, anglesDeg, skewsDeg, wave, yMode, yValues)
            if nargin < 5 || isempty(skewsDeg), skewsDeg = 0; end
            if nargin < 6, wave = 'longitudinal'; end
            if nargin < 7, yMode = 'from-skew'; end
            if nargin < 8, yValues = []; end
            if ~any(strcmp(mode, {'constant-depth', 'vertical-line', 'sound-path'}))
                error('FocalRules:input', 'Unknown focus mode "%s".', mode);
            end
            if ~any(strcmp(yMode, {'from-skew', 'fixed', 'sweep'}))
                error('FocalRules:input', 'Unknown Y mode "%s".', yMode);
            end
            if strcmp(yMode, 'fixed') && strcmp(mode, 'sound-path')
                error('FocalRules:input', 'A fixed Y over-constrains the sound-path focus.');
            end
            if ~strcmp(yMode, 'from-skew') && isempty(yValues)
                error('FocalRules:input', 'Y mode "%s" needs Y values.', yMode);
            end
            if strcmp(yMode, 'fixed') && numel(yValues) ~= 1
                error('FocalRules:input', 'A fixed Y takes one value.');
            end
            vWedge = solver.Wedge.Velocity;
            vMat = FocalRules.componentSpeed(solver.Material, wave);
            c = solver.apertureCentre();
            cx = c(1); cy = c(2); h = abs(c(3));
            pathSweep = strcmp(mode, 'sound-path') && strcmp(yMode, 'sweep');

            T = struct('Angle', {}, 'Skew', {}, 'X', {}, 'Y', {}, 'Z', {}, 'Reason', {});
            for ang = anglesDeg(:)'
                beta = deg2rad(ang);
                sinAlpha = vWedge / vMat * sin(beta);
                if abs(sinAlpha) > 1
                    for s = skewsDeg(:)'
                        T(end+1) = FocalRules.refused(ang, s, 'critical angle'); %#ok<AGROW>
                    end
                    continue
                end
                entry = h * tan(asin(sinAlpha));
                xInt = cx + entry;
                [fz, fPrimary, fx] = FocalRules.baseFocal(mode, value, beta, xInt);
                if ~isnan(fz) && fz < 0
                    for s = skewsDeg(:)'
                        T(end+1) = FocalRules.refused(ang, s, 'focus not below surface'); %#ok<AGROW>
                    end
                    continue
                end
                for s = skewsDeg(:)'
                    if pathSweep
                        reach = entry + fPrimary;
                        for y = yValues(:)'
                            if abs(reach) <= FocalRules.ZeroReach
                                % No horizontal reach: only the aperture centre's Y is on the ray.
                                if abs(y - cy) <= FocalRules.ZeroReach, v = 0; else, v = Inf; end
                            else
                                v = (y - cy) / reach;
                            end
                            if abs(v) > 1
                                T(end+1) = FocalRules.refused(ang, NaN, 'Y out of reach'); %#ok<AGROW>
                                continue
                            end
                            eff = asin(v);
                            T(end+1) = FocalRules.target(ang, rad2deg(eff), cx + reach * cos(eff), y, fz); %#ok<AGROW>
                        end
                        break   % the skew list is not used in this mode
                    end
                    sk = deg2rad(s);
                    xe = xInt + entry * (cos(sk) - 1);
                    ye = cy + entry * sin(sk);
                    switch mode
                        case 'constant-depth'
                            x = xe + fPrimary * cos(sk); z = fz; ys = ye + fPrimary * sin(sk);
                        case 'vertical-line'
                            if abs(cos(sk)) < FocalRules.ParallelTol || abs(tan(beta)) < FocalRules.ParallelTol
                                T(end+1) = FocalRules.refused(ang, s, 'beam parallel to line'); %#ok<AGROW>
                                continue
                            end
                            f3 = (fx - xe) / cos(sk);
                            x = fx; z = f3 / tan(beta); ys = ye + f3 * sin(sk);
                        otherwise   % sound-path
                            x = xe + fPrimary * cos(sk); z = fz; ys = ye + fPrimary * sin(sk);
                    end
                    if ~strcmp(yMode, 'from-skew') && ~strcmp(mode, 'sound-path')
                        ys = yValues(:)';
                    end
                    if ~(z > 0)
                        T(end+1) = FocalRules.refused(ang, s, 'focus not below surface'); %#ok<AGROW>
                        continue
                    end
                    for y = ys
                        T(end+1) = FocalRules.target(ang, s, x, y, z); %#ok<AGROW>
                    end
                end
            end
        end

        function v = componentSpeed(material, wave)
            %COMPONENTSPEED Component wave speed (m/s) for 'longitudinal' or 'shear'.
            switch lower(wave)
                case 'longitudinal'
                    v = material.VelocityLongitudinal;
                case 'shear'
                    if isempty(material.VelocityShear) || ~(material.VelocityShear > 0)
                        error('FocalRules:input', 'Shear mode requires a shear wave speed.');
                    end
                    v = material.VelocityShear;
                otherwise
                    error('FocalRules:input', 'Wave must be ''longitudinal'' or ''shear''.');
            end
        end
    end

    methods (Static, Access = private)
        function [fz, fPrimary, fx] = baseFocal(mode, value, beta, xInt)
            % Un-skewed primitives: depth, horizontal reach from the entry point, line X.
            fx = NaN;
            switch mode
                case 'constant-depth'
                    fz = value; fPrimary = value * tan(beta);
                case 'vertical-line'
                    fx = value;
                    if abs(tan(beta)) < FocalRules.ParallelTol
                        fz = NaN; fPrimary = 0;   % parallel: refused per skew
                    else
                        fPrimary = value - xInt; fz = fPrimary / tan(beta);
                    end
                otherwise
                    fz = value * cos(beta); fPrimary = value * sin(beta);
            end
        end

        function t = target(ang, skew, x, y, z)
            t = struct('Angle', ang, 'Skew', skew, 'X', x, 'Y', y, 'Z', z, 'Reason', '');
        end

        function t = refused(ang, skew, reason)
            t = struct('Angle', ang, 'Skew', skew, 'X', NaN, 'Y', NaN, 'Z', NaN, 'Reason', reason);
        end
    end
end
