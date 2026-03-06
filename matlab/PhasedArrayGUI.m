function PhasedArrayGUI()
    % PhasedArrayGUI: Matlab GUI for Phased Array Focal Law Calculator
    % Modernized and reformatted for readability and robustness.
    
    % Create Figure
    f = figure('Name', 'Phased Array Focal Law Calculator', ...
               'NumberTitle', 'off', ...
               'Position', [100, 100, 1200, 800], ...
               'MenuBar', 'none', ...
               'ToolBar', 'figure');
               
    % --- Helper Functions ---
    function h = addParam(y, label, val, tag)
        uicontrol('Style', 'text', 'String', label, ...
                  'Position', [20, y, 140, 20], ...
                  'HorizontalAlignment', 'right');
        h = uicontrol('Style', 'edit', 'String', num2str(val), ...
                      'Position', [170, y, 100, 20], ...
                      'Tag', tag, 'BackgroundColor', 'white');
    end

    function h = addCombo(y, label, items, tag)
        uicontrol('Style', 'text', 'String', label, ...
                  'Position', [20, y, 140, 20], ...
                  'HorizontalAlignment', 'right');
        h = uicontrol('Style', 'popupmenu', 'String', items, ...
                      'Position', [170, y, 100, 20], ...
                      'Tag', tag);
    end

    % --- UI Layout ---
    uicontrol('Style', 'text', 'String', 'Probe Settings', ...
              'Position', [20, 760, 200, 20], ...
              'FontWeight', 'bold', 'HorizontalAlignment', 'left');
              
    y = 730;
    h_numEl = addParam(y, 'Num Elements:', 16, 'numEl');
    y = y - 30;
    h_pitch = addParam(y, 'Pitch (mm):', 0.6, 'pitch');
    y = y - 30;

    uicontrol('Style', 'text', 'String', 'Wedge Settings', ...
              'Position', [20, y, 200, 20], ...
              'FontWeight', 'bold', 'HorizontalAlignment', 'left');
    y = y - 30;

    h_wAngle = addParam(y, 'Angle (deg):', 36.0, 'wAngle');
    y = y - 30;
    h_wHeight = addParam(y, 'Height @ El.1 (mm):', 15.0, 'wHeight');
    y = y - 30;
    h_wVel = addParam(y, 'Velocity (m/s):', 2330.0, 'wVel');
    y = y - 30;

    uicontrol('Style', 'text', 'String', 'Material Settings', ...
              'Position', [20, y, 200, 20], ...
              'FontWeight', 'bold', 'HorizontalAlignment', 'left');
    y = y - 30;

    h_mVelL = addParam(y, 'L-Wave Vel (m/s):', 5920.0, 'mVelL');
    y = y - 30;
    h_mVelS = addParam(y, 'S-Wave Vel (m/s):', 3240.0, 'mVelS');
    y = y - 30;

    uicontrol('Style', 'text', 'String', 'Scan Settings', ...
              'Position', [20, y, 200, 20], ...
              'FontWeight', 'bold', 'HorizontalAlignment', 'left');
    y = y - 30;

    h_focusMode = addCombo(y, 'Focus Type:', {'Constant Depth', 'Vertical Line', 'Constant Sound Path'}, 'focusMode');
    y = y - 30;
    h_waveType = addCombo(y, 'Wave Type:', {'Longitudinal', 'Shear'}, 'waveType');
    y = y - 30;

    h_startAng = addParam(y, 'Start Angle (deg):', 40.0, 'startAng');
    y = y - 30;
    h_endAng = addParam(y, 'End Angle (deg):', 70.0, 'endAng');
    y = y - 30;
    h_stepAng = addParam(y, 'Step (deg):', 1.0, 'stepAng');
    y = y - 30;

    h_target = addParam(y, 'Target X (Global, mm):', 50.0, 'targetVal');
    y = y - 40;

    btn_calc = uicontrol('Style', 'pushbutton', 'String', 'Calculate', ...
                         'Position', [100, y, 150, 40], ...
                         'Callback', @runCalculation, ...
                         'FontWeight', 'bold', 'FontSize', 12);

    ax = axes('Position', [0.35, 0.1, 0.60, 0.8]);
    grid(ax, 'on');
    axis(ax, 'equal');
    set(ax, 'YDir', 'reverse');
    xlabel(ax, 'X (mm)');
    ylabel(ax, 'Z Depth (mm)');
    title(ax, 'Ray Tracing');

    % --- Calculation Callback ---
    function runCalculation(~, ~)
        try
            % 1. Gather Inputs
            nEl = str2double(get(h_numEl, 'String'));
            pPitch = str2double(get(h_pitch, 'String')) / 1000;
            wAng = str2double(get(h_wAngle, 'String'));
            wH = str2double(get(h_wHeight, 'String')) / 1000;
            wV = str2double(get(h_wVel, 'String'));
            mVL = str2double(get(h_mVelL, 'String'));
            mVS = str2double(get(h_mVelS, 'String'));
            startA = str2double(get(h_startAng, 'String'));
            endA = str2double(get(h_endAng, 'String'));
            stepA = str2double(get(h_stepAng, 'String'));
            tgtVal = str2double(get(h_target, 'String')) / 1000;

            fModeIdx = get(h_focusMode, 'Value');
            fModeOpts = {'Depth', 'Vertical', 'SoundPath'};
            fMode = fModeOpts{fModeIdx};

            wTypeIdx = get(h_waveType, 'Value');
            wTypeOpts = {'longitudinal', 'shear'};
            wType = wTypeOpts{wTypeIdx};

            % 2. Setup Objects
            probe = Probe(nEl, pPitch, 5e6);
            wedge = Wedge(wAng, wH, wV, 0);
            mat = Material(mVL, mVS);
            solver = DelayLaw(probe, wedge, mat);

            vMat = mVL;
            if strcmp(wType, 'shear')
                vMat = mVS;
            end

            angles = startA:stepA:endA;

            % Plot Setup
            cla(ax);
            hold(ax, 'on');
            yline(ax, 0, 'k-', 'LineWidth', 2); % Interface

            elements = wedge.getTransformedElements(probe);
            plot(ax, elements(:, 1) * 1000, elements(:, 2) * 1000, 'rs', 'MarkerSize', 4);

            % Wedge Polygon
            elX = elements(:, 1);
            p1 = elements(1, :);
            p2 = elements(end, :);

            if abs(p2(1) - p1(1)) > 1e-9
                m_slope = (p2(2) - p1(2)) / (p2(1) - p1(1));
                c_off = p1(2) - m_slope * p1(1);
            else
                m_slope = 0;
                c_off = p1(2);
            end

            wMinX = min(elX) - 0.015;
            wMaxX = max(elX) + 0.015;
            zL = min(m_slope * wMinX + c_off, 0);
            zR = min(m_slope * wMaxX + c_off, 0);

            patch(ax, [wMinX, wMaxX, wMaxX, wMinX] * 1000, ...
                      [0, 0, zR, zL] * 1000, 'c', ...
                  'FaceAlpha', 0.2, 'EdgeColor', 'none');

            centerX = (elements(1, 1) + elements(end, 1)) / 2;
            colors = jet(length(angles));

            validCount = 0;

            for i = 1:length(angles)
                angDeg = angles(i);
                beta = deg2rad(angDeg);
                sinAlpha = (wV / vMat) * sin(beta);

                if abs(sinAlpha) > 1.0
                    continue;
                end

                alpha = asin(sinAlpha);
                centerZ = (elements(1, 2) + elements(end, 2)) / 2;
                xInt = centerX + (-centerZ) * tan(alpha);

                if strcmp(fMode, 'Depth')
                    fz = tgtVal;
                    fx = xInt + fz * tan(beta);
                elseif strcmp(fMode, 'Vertical')
                    fx = tgtVal;
                    fz = (fx - xInt) / tan(beta);
                else
                    R = tgtVal;
                    fx = xInt + R * sin(beta);
                    fz = R * cos(beta);
                end

                if fz < 0
                    continue;
                end

                res = solver.calculateLaw(fx, fz, wType);
                intPts = res.InterfacePoints;
                c = colors(i, :);

                % Plot Rays
                plot(ax, [elements(1, 1), intPts(1, 1)] * 1000, ...
                         [elements(1, 2), intPts(1, 2)] * 1000, 'Color', c);
                plot(ax, [intPts(1, 1), fx] * 1000, ...
                         [intPts(1, 2), fz] * 1000, 'Color', c);
                plot(ax, [elements(end, 1), intPts(end, 1)] * 1000, ...
                         [elements(end, 2), intPts(end, 2)] * 1000, 'Color', c);
                plot(ax, [intPts(end, 1), fx] * 1000, ...
                         [intPts(end, 2), fz] * 1000, 'Color', c);

                validCount = validCount + 1;
            end

            if validCount == 0
                errordlg('No valid focal laws calculated. Check geometry.', 'Warning');
            end

            axis(ax, 'equal');
            set(ax, 'YDir', 'reverse');

        catch err
            errordlg(err.message, 'Calculation Error');
        end
    end
end
