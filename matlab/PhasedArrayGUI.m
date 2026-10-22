function PhasedArrayGUI()
    % PhasedArrayGUI: MATLAB GUI for Phased Array Focal Law Calculator
    % Supports Linear, Matrix, Dual Linear, and Dual Matrix probe types.
    % 3D focal law calculation with skew sweep and Y focus modes.
    
    % ===================== Figure =====================
    figW = 1400; figH = 900;
    f = figure('Name', 'Phased Array Focal Law Calculator', ...
               'NumberTitle', 'off', ...
               'Position', [50, 50, figW, figH], ...
               'MenuBar', 'none', ...
               'ToolBar', 'figure');

    % ===================== Layout constants =====================
    R  = 24;    % row pitch (px)
    LX = 10;    % label x
    LW = 148;   % label width
    FX = 162;   % field x
    FW = 108;   % field width

    % ===================== Helper functions =====================
    function h = addParam(y, label, val, tag)
        uicontrol(f, 'Style', 'text', 'String', label, ...
                  'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
        h = uicontrol(f, 'Style', 'edit', 'String', num2str(val), ...
                      'Position', [FX, y, FW, 22], ...
                      'Tag', tag, 'BackgroundColor', 'white');
    end

    function h = addCombo(y, label, items, tag)
        uicontrol(f, 'Style', 'text', 'String', label, ...
                  'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
        h = uicontrol(f, 'Style', 'popupmenu', 'String', items, ...
                      'Position', [FX, y, FW, 22], 'Tag', tag);
    end

    function addSec(y, txt)
        uicontrol(f, 'Style', 'text', 'String', txt, ...
                  'Position', [LX, y, 270, 20], ...
                  'FontWeight', 'bold', 'HorizontalAlignment', 'left');
    end

    % ===================== UI Layout =====================
    % Start near top of 900px figure; 24px rows let everything fit
    y = figH - 26;

    % --- Probe Settings ---
    addSec(y, 'Probe Settings'); y = y - R;
    h_probeType = addCombo(y, 'Probe Type:', {'Linear', 'Matrix', 'Dual Linear', 'Dual Matrix'}, 'probeType');
    set(h_probeType, 'Callback', @onProbeTypeChange); y = y - R;
    h_numEl = addParam(y, 'Num Elements:', 16, 'numEl');  y = y - R;
    h_pitch  = addParam(y, 'Pitch (mm):', 0.6, 'pitch');  y = y - R;

    % Matrix-only
    lbl_nElY = uicontrol(f, 'Style', 'text', 'String', 'Passive Els (Y):', ...
                         'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
    h_nElY   = uicontrol(f, 'Style', 'edit', 'String', '1', ...
                         'Position', [FX, y, FW, 22], 'BackgroundColor', 'white'); y = y - R;
    lbl_pitchY = uicontrol(f, 'Style', 'text', 'String', 'Passive Pitch (mm):', ...
                           'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
    h_pitchY   = uicontrol(f, 'Style', 'edit', 'String', '0.6', ...
                           'Position', [FX, y, FW, 22], 'BackgroundColor', 'white'); y = y - R;

    % --- Wedge Settings ---
    addSec(y, 'Wedge Settings'); y = y - R;
    h_wAngle  = addParam(y, 'Angle (deg):', 36.0, 'wAngle');        y = y - R;
    h_wHeight = addParam(y, 'Height @ El.1 (mm):', 15.0, 'wHeight'); y = y - R;
    h_wVel    = addParam(y, 'Velocity (m/s):', 2330.0, 'wVel');     y = y - R;

    % Dual-only
    lbl_arraySep = uicontrol(f, 'Style', 'text', 'String', 'Array Sep. (mm):', ...
                             'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
    h_arraySep   = uicontrol(f, 'Style', 'edit', 'String', '0.0', ...
                             'Position', [FX, y, FW, 22], 'BackgroundColor', 'white'); y = y - R;
    lbl_roofAng = uicontrol(f, 'Style', 'text', 'String', 'Roof Angle (deg):', ...
                            'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
    h_roofAng   = uicontrol(f, 'Style', 'edit', 'String', '0.0', ...
                            'Position', [FX, y, FW, 22], 'BackgroundColor', 'white'); y = y - R;

    % --- Material Settings ---
    addSec(y, 'Material Settings'); y = y - R;
    h_mVelL = addParam(y, 'L-Wave Vel (m/s):', 5920.0, 'mVelL'); y = y - R;
    h_mVelS = addParam(y, 'S-Wave Vel (m/s):', 3240.0, 'mVelS'); y = y - R;
    h_thickness = addParam(y, 'Thickness (mm):', 0.0, 'thickness'); y = y - R;

    % --- Scan Settings ---
    addSec(y, 'Scan Settings'); y = y - R;
    h_focusMode = addCombo(y, 'Focus Type:', {'Constant Depth', 'Vertical Line', 'Constant Sound Path'}, 'focusMode'); y = y - R;
    h_waveType  = addCombo(y, 'Wave Type:', {'Longitudinal', 'Shear'}, 'waveType'); y = y - R;
    h_startAng  = addParam(y, 'Start Angle (deg):', 40.0, 'startAng'); y = y - R;
    h_endAng    = addParam(y, 'End Angle (deg):', 70.0, 'endAng');    y = y - R;
    h_stepAng   = addParam(y, 'Step (deg):', 1.0, 'stepAng');         y = y - R;

    % Skew (Matrix / Dual Matrix only)
    lbl_startSkew = uicontrol(f, 'Style', 'text', 'String', 'Start Skew (deg):', ...
                              'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
    h_startSkew   = uicontrol(f, 'Style', 'edit', 'String', '0.0', ...
                              'Position', [FX, y, FW, 22], 'BackgroundColor', 'white'); y = y - R;
    lbl_endSkew = uicontrol(f, 'Style', 'text', 'String', 'End Skew (deg):', ...
                            'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
    h_endSkew   = uicontrol(f, 'Style', 'edit', 'String', '0.0', ...
                            'Position', [FX, y, FW, 22], 'BackgroundColor', 'white'); y = y - R;
    lbl_stepSkew = uicontrol(f, 'Style', 'text', 'String', 'Skew Step (deg):', ...
                             'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
    h_stepSkew   = uicontrol(f, 'Style', 'edit', 'String', '1.0', ...
                             'Position', [FX, y, FW, 22], 'BackgroundColor', 'white'); y = y - R;

    h_target = addParam(y, 'Target (mm):', 50.0, 'targetVal'); y = y - R;

    % --- Sub-Aperture Settings ---
    addSec(y, 'Sub-Aperture Settings'); y = y - R;
    h_startEl   = addParam(y, 'Start Element:', 1, 'startEl'); y = y - R;
    h_numActive = addParam(y, 'Active Elements:', 0, 'numActive');
    uicontrol(f, 'Style', 'text', 'String', '(0 = All)', ...
              'Position', [FX + FW + 2, y, 60, 18], 'FontSize', 7); y = y - R;
    lbl_elOrder = uicontrol(f, 'Style', 'text', 'String', 'Element Order:', ...
                            'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
    h_elOrder   = uicontrol(f, 'Style', 'popupmenu', 'String', {'Column-first', 'Row-first'}, ...
                            'Position', [FX, y, FW, 22]); y = y - R;

    % --- Status & Buttons ---
    lbl_status = uicontrol(f, 'Style', 'text', 'String', 'Ready.', ...
                           'Position', [LX, y, 270, 20], ...
                           'FontWeight', 'bold', 'ForegroundColor', [0 0.5 0], ...
                           'HorizontalAlignment', 'center'); y = y - (R + 4);

    uicontrol(f, 'Style', 'pushbutton', 'String', 'Calculate', ...
              'Position', [55, y, 170, 32], ...
              'Callback', @runCalculation, ...
              'FontWeight', 'bold', 'FontSize', 11); y = y - (R + 4);

    uicontrol(f, 'Style', 'text', 'String', 'Export Format:', ...
              'Position', [LX, y, LW, 20], 'HorizontalAlignment', 'right');
    h_exportType = uicontrol(f, 'Style', 'popupmenu', 'String', {'CSV', 'MAT'}, ...
                             'Position', [FX, y, FW, 22]); y = y - R;

    btn_export = uicontrol(f, 'Style', 'pushbutton', 'String', 'Export Laws', ...
                           'Position', [LX + 4, y, 118, 26], ...
                           'Callback', @exportLaws, 'Enable', 'off', 'FontWeight', 'bold');
    btn_exportEls = uicontrol(f, 'Style', 'pushbutton', 'String', 'Export Elements', ...
                              'Position', [LX + 130, y, 138, 26], ...
                              'Callback', @exportElements, 'Enable', 'off', 'FontWeight', 'bold');

    % ===================== Plot Axes =====================
    sideN = 0.206;   % sidebar normalised width (280 / 1400 ≈ 0.20, +margin)

    ax_xz = axes(f, 'Position', [sideN + 0.01, 0.33, 0.375, 0.58]);
    grid(ax_xz, 'on'); axis(ax_xz, 'equal'); set(ax_xz, 'YDir', 'reverse');
    xlabel(ax_xz, 'X (mm)'); ylabel(ax_xz, 'Z Depth (mm)');
    title(ax_xz, 'Ray Tracing X-Z');

    ax_yz = axes(f, 'Position', [sideN + 0.405, 0.33, 0.375, 0.58]);
    grid(ax_yz, 'on'); axis(ax_yz, 'equal'); set(ax_yz, 'YDir', 'reverse');
    xlabel(ax_yz, 'Y (mm)'); ylabel(ax_yz, 'Z Depth (mm)');
    title(ax_yz, 'Ray Tracing Y-Z');

    % Delay profile bar chart (bottom strip, below the sliders)
    ax_delay = axes(f, 'Position', [sideN + 0.01, 0.05, 0.770, 0.14]);
    grid(ax_delay, 'on');
    xlabel(ax_delay, 'Element ID'); ylabel(ax_delay, 'Delay (\mus)');
    title(ax_delay, 'Delay Profile');

    % Azimuth Slider
    sliderX = round(sideN * figW) + 10;
    sliderW = figW - sliderX - 20;
    lbl_az = uicontrol(f, 'Style', 'text', 'String', 'Angle: 0.0 deg', ...
                       'Position', [sliderX, 225, 120, 20], 'HorizontalAlignment', 'left');
    slider_az = uicontrol(f, 'Style', 'slider', ...
                          'Position', [sliderX + 130, 225, sliderW - 130, 20], ...
                          'Min', 0, 'Max', 1, 'Value', 0, 'Callback', @onSliderChange);

    % Skew Slider
    lbl_sk = uicontrol(f, 'Style', 'text', 'String', 'Skew: 0.0 deg', ...
                       'Position', [sliderX, 198, 120, 20], 'HorizontalAlignment', 'left');
    slider_sk = uicontrol(f, 'Style', 'slider', ...
                          'Position', [sliderX + 130, 198, sliderW - 130, 20], ...
                          'Min', 0, 'Max', 1, 'Value', 0, 'Callback', @onSliderChange);

    % --- State Variables ---
    lastScanData = [];
    lastSolver = [];
    allResults = [];
    angleValues = [];
    skewValues = [];
    indexMap = containers.Map('KeyType', 'char', 'ValueType', 'int32');
    currentProbeType = 'Linear';
    
    % Initial visibility
    onProbeTypeChange();
    
    % ===================== Callbacks =====================
    
    function onProbeTypeChange(~, ~)
        idx = get(h_probeType, 'Value');
        types = {'Linear', 'Matrix', 'Dual Linear', 'Dual Matrix'};
        currentProbeType = types{idx};
        
        isMatrix = ismember(currentProbeType, {'Matrix', 'Dual Matrix'});
        isDual = ismember(currentProbeType, {'Dual Linear', 'Dual Matrix'});
        isLinear = strcmp(currentProbeType, 'Linear');
        
        % Matrix fields
        vis = 'off'; if isMatrix; vis = 'on'; end
        set(lbl_nElY, 'Visible', vis); set(h_nElY, 'Visible', vis);
        set(lbl_pitchY, 'Visible', vis); set(h_pitchY, 'Visible', vis);
        
        % Dual fields
        vis = 'off'; if isDual; vis = 'on'; end
        set(lbl_arraySep, 'Visible', vis); set(h_arraySep, 'Visible', vis);
        set(lbl_roofAng, 'Visible', vis); set(h_roofAng, 'Visible', vis);
        
        % Skew fields
        vis = 'off'; if isMatrix; vis = 'on'; end
        set(lbl_startSkew, 'Visible', vis); set(h_startSkew, 'Visible', vis);
        set(lbl_endSkew, 'Visible', vis);   set(h_endSkew, 'Visible', vis);
        set(lbl_stepSkew, 'Visible', vis);  set(h_stepSkew, 'Visible', vis);
        
        % Element Order (matrix only)
        set(lbl_elOrder, 'Visible', vis); set(h_elOrder, 'Visible', vis);
        
        % Skew slider
        vis = 'off'; if isMatrix; vis = 'on'; end
        set(lbl_sk, 'Visible', vis); set(slider_sk, 'Visible', vis);
        
        % Y-Z axes
        if isLinear
            set(ax_yz, 'Visible', 'off');
            set(ax_xz, 'Position', [0.216, 0.33, 0.767, 0.58]);
        else
            set(ax_yz, 'Visible', 'on');
            set(ax_xz, 'Position', [0.216, 0.33, 0.375, 0.58]);
        end
    end
    
    function onSliderChange(~, ~)
        if isempty(angleValues); return; end
        
        iAz = round(get(slider_az, 'Value'));
        iAz = max(1, min(iAz, length(angleValues)));
        
        iSk = round(get(slider_sk, 'Value'));
        iSk = max(1, min(iSk, length(skewValues)));
        
        set(lbl_az, 'String', sprintf('Angle: %.1f deg', angleValues(iAz)));
        set(lbl_sk, 'String', sprintf('Skew: %.1f deg', skewValues(iSk)));
        
        refreshPlot(iAz, iSk);
    end
    
    function refreshPlot(iAz, iSk)
        if isempty(allResults); return; end

        key = sprintf('%.4f_%.4f', angleValues(iAz), skewValues(iSk));
        if ~isKey(indexMap, key); return; end
        idx = indexMap(key);

        res = allResults(idx);
        probe = lastSolver.Probe;
        elements = lastSolver.Wedge.getTransformedElements(probe);

        isDualProbe = isa(probe, 'DualProbe');
        isLinear = strcmp(currentProbeType, 'Linear');
        nHalf = size(elements, 1) / 2;

        % Active element indices: prefer the ones stored with this law
        % (sub-aperture aware) and fall back to the probe's current
        % setting only if an older result entry lacks them.
        if isfield(res, 'ActiveIndices') && ~isempty(res.ActiveIndices)
            activeIndices = res.ActiveIndices;
        else
            activeIndices = probe.getActiveElementIndices();
        end

        thicknessMM = str2double(get(h_thickness, 'String'));
        if isnan(thicknessMM) || thicknessMM < 0
            thicknessMM = 0;
        end

        wedgeAngDeg = lastSolver.Wedge.AngleDegrees;

        % --- X-Z Plot ---
        titleXZ = sprintf('X-Z  Angle: %.1f  Skew: %.1f', res.Angle, res.Skew);
        [legH, legL] = plotProjection(ax_xz, 1, true, elements, res.InterfacePoints, ...
            res.FocalPoint, activeIndices, isDualProbe, nHalf, wedgeAngDeg, thicknessMM, ...
            'X (mm)', titleXZ);
        if ~isempty(legH)
            legend(ax_xz, legH, legL, 'Location', 'northeast', 'FontSize', 7);
        end

        % --- Y-Z Plot ---
        if ~isLinear
            plotProjection(ax_yz, 2, false, elements, res.InterfacePoints, ...
                res.FocalPoint, activeIndices, isDualProbe, nHalf, wedgeAngDeg, thicknessMM, ...
                'Y (mm)', 'Y-Z Projection');
        end

        % --- Delay Profile Bar Chart ---
        delaysUs = res.Delays * 1e6;
        cla(ax_delay);
        bar(ax_delay, 1:numel(delaysUs), delaysUs, 'FaceColor', [0.53 0.81 0.92], 'EdgeColor', 'k');
        xlabel(ax_delay, 'Element ID'); ylabel(ax_delay, 'Delay (\mus)');
        title(ax_delay, sprintf('Delay Profile - Angle: %.1f  Skew: %.1f', res.Angle, res.Skew));
        grid(ax_delay, 'on');

        globalMaxDelay = 0;
        for k = 1:numel(allResults)
            dk = max(allResults(k).Delays) * 1e6;
            if ~isnan(dk) && dk > globalMaxDelay
                globalMaxDelay = dk;
            end
        end
        if globalMaxDelay > 0
            ylim(ax_delay, [0, 1.1 * globalMaxDelay]);
        end
    end
    
    % ===================== Calculation =====================
    
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
            
            idx = get(h_probeType, 'Value');
            pTypes = {'Linear', 'Matrix', 'Dual Linear', 'Dual Matrix'};
            pType = pTypes{idx};
            
            isMatrix = ismember(pType, {'Matrix', 'Dual Matrix'});
            
            nElY = 1; pitchY = 0; arraySep = 0; roofAng = 0;
            if ismember(pType, {'Matrix', 'Dual Matrix'})
                nElY = str2double(get(h_nElY, 'String'));
                pitchY = str2double(get(h_pitchY, 'String')) / 1000;
            end
            if ismember(pType, {'Dual Linear', 'Dual Matrix'})
                arraySep = str2double(get(h_arraySep, 'String')) / 1000;
                roofAng = str2double(get(h_roofAng, 'String'));
            end
            
            % Sub-aperture
            startEl = str2double(get(h_startEl, 'String'));
            numActive = str2double(get(h_numActive, 'String'));
            elOrderIdx = get(h_elOrder, 'Value');
            elOrderOpts = {'column-first', 'row-first'};
            elOrder = elOrderOpts{elOrderIdx};
            
            % 2. Setup Objects
            if ismember(pType, {'Dual Linear', 'Dual Matrix'})
                probe = DualProbe(nEl, pPitch, 5e6, nElY, pitchY, arraySep, startEl, numActive, elOrder);
            else
                probe = Probe(nEl, pPitch, 5e6, nElY, pitchY, startEl, numActive, elOrder);
            end
            
            wedge = Wedge(wAng, wH, wV, 0, roofAng);
            mat = Material(mVL, mVS);
            solver = DelayLaw(probe, wedge, mat);
            
            vMat = mVL;
            if strcmp(wType, 'shear'); vMat = mVS; end
            
            % 3. Angles and Skew
            angles = startA:stepA:endA;
            
            if isMatrix
                sStart = str2double(get(h_startSkew, 'String'));
                sEnd = str2double(get(h_endSkew, 'String'));
                sStep = str2double(get(h_stepSkew, 'String'));
                if sStep > 0
                    skewAngles = sStart:sStep:sEnd;
                else
                    skewAngles = sStart;
                end
            else
                skewAngles = 0;
            end
            
            % 4. Compute
            elements = wedge.getTransformedElements(probe);
            centerX = mean(elements(:, 1));
            centerY = mean(elements(:, 2));
            centerZ = mean(elements(:, 3));
            hWedge = abs(centerZ);
            
            resultIdx = 0;
            allResults = [];
            angleValues = unique(angles);
            skewValues = unique(skewAngles);
            indexMap = containers.Map('KeyType', 'char', 'ValueType', 'int32');
            
            for i = 1:length(angles)
                angDeg = angles(i);
                beta = deg2rad(angDeg);
                sinAlpha = (wV / vMat) * sin(beta);
                
                if abs(sinAlpha) > 1.0; continue; end
                
                alpha = asin(sinAlpha);
                xInt = centerX + hWedge * tan(alpha);
                
                if strcmp(fMode, 'Depth')
                    fz = tgtVal;
                    fPrimary = fz * tan(beta);
                elseif strcmp(fMode, 'Vertical')
                    fx_target = tgtVal;
                    fPrimary = fx_target - xInt;
                    fz = fPrimary / tan(beta);
                else % SoundPath
                    R = tgtVal;
                    fz = R * cos(beta);
                    fPrimary = R * sin(beta);
                end
                
                if fz < 0; continue; end
                
                for j = 1:length(skewAngles)
                    skewDeg = skewAngles(j);
                    skewRad = deg2rad(skewDeg);
                    
                    lx = xInt + fPrimary * cos(skewRad);
                    ly = centerY + fPrimary * sin(skewRad);
                    
                    res = solver.calculateLaw(lx, ly, fz, wType);
                    
                    resultIdx = resultIdx + 1;
                    
                    entry.Angle = angDeg;
                    entry.Skew = skewDeg;
                    entry.FocalPoint = [lx, ly, fz];
                    entry.Delays = res.Delays;
                    entry.InterfacePoints = res.InterfacePoints;
                    entry.VelocityUsed = res.VelocityUsed;
                    entry.ActiveIndices = res.ActiveIndices;
                    
                    if resultIdx == 1
                        allResults = entry;
                    else
                        allResults(resultIdx) = entry;
                    end
                    
                    key = sprintf('%.4f_%.4f', angDeg, skewDeg);
                    indexMap(key) = resultIdx;
                end
            end
            
            % 5. Update State
            lastScanData = allResults;
            lastSolver = solver;
            
            if resultIdx == 0
                errordlg('No valid focal laws calculated.', 'Warning');
                set(btn_export, 'Enable', 'off');
                return;
            end
            
            set(btn_export, 'Enable', 'on');
            set(btn_exportEls, 'Enable', 'on');
            
            % 6. Update Sliders
            set(slider_az, 'Min', 1, 'Max', max(1, length(angleValues)), 'Value', 1);
            set(slider_sk, 'Min', 1, 'Max', max(1, length(skewValues)), 'Value', 1);
            
            if length(angleValues) > 1
                set(slider_az, 'SliderStep', [1/(length(angleValues)-1), 1/(length(angleValues)-1)]);
            end
            if length(skewValues) > 1
                set(slider_sk, 'SliderStep', [1/(length(skewValues)-1), 1/(length(skewValues)-1)]);
            end
            
            set(lbl_az, 'String', sprintf('Angle: %.1f deg', angleValues(1)));
            set(lbl_sk, 'String', sprintf('Skew: %.1f deg', skewValues(1)));
            
            refreshPlot(1, 1);
            
            set(lbl_status, 'String', sprintf('Success: %d focal laws calculated.', resultIdx));
            
        catch err
            errordlg(err.message, 'Calculation Error');
        end
    end

    % ===================== Export =====================
    
    function exportLaws(~, ~)
        if isempty(lastScanData); return; end
        
        formatIdx = get(h_exportType, 'Value');
        formats = {'CSV', 'MAT'};
        fmt = formats{formatIdx};
        
        if strcmp(fmt, 'MAT')
            [file, path] = uiputfile('*.mat', 'Save Focal Laws As');
            if isequal(file, 0); return; end
            
            fullname = fullfile(path, file);
            scanData = lastScanData; %#ok<NASGU>
            save(fullname, 'scanData');
            msgbox(sprintf('Exported to %s', fullname), 'Success');
        else
            [file, path] = uiputfile('*.csv', 'Save Focal Laws As');
            if isequal(file, 0); return; end
            
            fullname = fullfile(path, file);
            fid = fopen(fullname, 'w');
            
            numEls = length(lastScanData(1).Delays);
            headerList = {'LawID', 'Angle_Deg', 'Skew_Deg', 'Fx_mm', 'Fy_mm', 'Fz_mm', 'Velocity_m_s'};
            for i = 1:numEls
                headerList{end+1} = sprintf('El_%d_us', i); %#ok<AGROW>
            end
            fprintf(fid, '%s\n', strjoin(headerList, ','));
            
            for i = 1:length(lastScanData)
                law = lastScanData(i);
                if isempty(law.Angle); continue; end
                
                fprintf(fid, '%d,%.2f,%.2f,%.4f,%.4f,%.4f,%.2f', i, law.Angle, ...
                        law.Skew, law.FocalPoint(1)*1000, law.FocalPoint(2)*1000, ...
                        law.FocalPoint(3)*1000, law.VelocityUsed);
                
                delaysUs = law.Delays * 1e6;
                for j = 1:length(delaysUs)
                    fprintf(fid, ',%.4f', delaysUs(j));
                end
                fprintf(fid, '\n');
            end
            fclose(fid);
            msgbox(sprintf('Exported to %s', fullname), 'Success');
        end
    end

    function exportElements(~, ~)
        if isempty(lastSolver); return; end
        
        [file, path] = uiputfile({'*.csv', 'CSV File (*.csv)'; ...
                                  '*.mat', 'MATLAB Data (*.mat)'; ...
                                  '*.m', 'MATLAB Script (*.m)'}, ...
                                  'Save Element Coordinates As');
        if isequal(file, 0); return; end
        
        fullname = fullfile(path, file);
        lastSolver.exportElementPositions(fullname);
        msgbox(sprintf('Exported elements to %s', fullname), 'Success');
    end
end

% =====================================================================
% Local (non-nested) drawing helpers for refreshPlot.
% Mirrors python/scene.py: draw_wedge_overlay, draw_elements,
% draw_law_rays, finish_projection.
% =====================================================================

function pairs = localActiveEnvelopePairs(activeIndices, isDualProbe, nHalf)
    % Returns an Mx2 array of [firstIdx, lastIdx] envelope pairs
    % (1-based), one row per Tx/Rx half for dual probes (split at
    % nHalf), or a single row for a single array. Halves with no
    % active elements are omitted.
    act = sort(activeIndices(:));
    pairs = zeros(0, 2);
    if isempty(act)
        return;
    end
    if isDualProbe
        tx = act(act <= nHalf);
        rx = act(act > nHalf);
        if ~isempty(tx)
            pairs(end+1, :) = [tx(1), tx(end)];
        end
        if ~isempty(rx)
            pairs(end+1, :) = [rx(1), rx(end)];
        end
    else
        pairs(end+1, :) = [act(1), act(end)];
    end
end

function geom = localWedgeGeometry(ec, ez, isXZ, wedgeAngDeg)
    % Computes wedge/probe polygon vertices (mm) and annotation anchors
    % from transformed element coordinates. Mirrors
    % python/scene.py:draw_wedge_overlay exactly (contact detection,
    % sloped/flat wedge silhouette, front-face capping, schematic probe
    % body). dimIsXZ selects the sloped X-Z silhouette vs. the plain
    % rectangular Y-Z silhouette; no probe body / annotations for Y-Z.
    geom.isContact = max(abs(ez)) < 1e-3;
    geom.contactX = min(ec);
    geom.wedgeVerts = zeros(0, 2);
    geom.probeVerts = zeros(0, 2);
    geom.h1El = [ec(1), ez(1)];
    geom.angleTextPos = [];
    geom.wedgeAngDeg = wedgeAngDeg;

    if geom.isContact
        return;
    end

    span = max(ec) - min(ec);
    margin = max(2.0, 0.15 * span);

    if ~isXZ
        zTop = min(ez);
        geom.wedgeVerts = [min(ec)-margin, 0.0; max(ec)+margin, 0.0; ...
                           max(ec)+margin, zTop; min(ec)-margin, zTop];
        return;
    end

    tanA = tand(wedgeAngDeg);
    if tanA > 1e-6
        % Top-face silhouette line z(x) = -tanA*x + c through the
        % highest elements (covers roof-angled duals too).
        c = min(ez + tanA * ec);
        xToe = c / tanA;           % z = 0 crossing of the top-face line
        xBack = max(ec) + margin;
        zBack = -tanA * xBack + c;

        % Cap a very long toe with a vertical front face so a shallow
        % wedge doesn't dominate the frame.
        xFrontCap = min(ec) - 4.0 * margin;
        if xToe < xFrontCap
            zFront = -tanA * xFrontCap + c;
            verts = [xFrontCap, 0.0; xBack, 0.0; xBack, zBack; xFrontCap, zFront];
        else
            verts = [xToe, 0.0; xBack, 0.0; xBack, zBack];
        end
        zAt = @(x) -tanA * x + c;
    else
        % Flat wedge (delay line): rectangle
        zTop = min(ez);
        verts = [min(ec)-margin, 0.0; max(ec)+margin, 0.0; ...
                 max(ec)+margin, zTop; min(ec)-margin, zTop];
        zAt = @(x) zTop;
    end
    geom.wedgeVerts = verts;

    % Schematic probe body sitting on the top face over the element extent
    x0 = min(ec); x1 = max(ec);
    hp = max(3.0, 0.25 * abs(min(ez)));
    geom.probeVerts = [x0, zAt(x0); x1, zAt(x1); x1, zAt(x1)-hp; x0, zAt(x0)-hp];

    % Dimension annotation anchors: h1 drop line at element 1, and the
    % wedge angle centred above the wedge top.
    xMid = 0.5 * (min(verts(:,1)) + max(verts(:,1)));
    zTopWedge = min(verts(:,2));
    geom.angleTextPos = [xMid, zTopWedge - 1.0];
end

function [hWedge, hProbe] = localDrawWedge(ax, geom)
    % Draws the wedge body, schematic probe body, and dimension
    % annotations described by geom (see localWedgeGeometry). Returns
    % the wedge/probe patch handles (empty if not drawn, e.g. contact).
    COL_WEDGE_FACE = [0.13 0.77 0.37];
    COL_WEDGE_EDGE = [0.08 0.50 0.24];
    COL_PROBE_FACE = [0.39 0.45 0.55];
    COL_PROBE_EDGE = [0.20 0.26 0.33];

    hWedge = [];
    hProbe = [];

    if geom.isContact
        text(ax, geom.contactX, -1.2, 'Contact', 'FontSize', 7, 'Color', COL_PROBE_EDGE);
        return;
    end

    if ~isempty(geom.wedgeVerts)
        hWedge = patch(ax, geom.wedgeVerts(:,1), geom.wedgeVerts(:,2), COL_WEDGE_FACE, ...
                       'FaceAlpha', 0.16, 'EdgeColor', COL_WEDGE_EDGE, 'LineWidth', 1.0);
    end
    if ~isempty(geom.probeVerts)
        hProbe = patch(ax, geom.probeVerts(:,1), geom.probeVerts(:,2), COL_PROBE_FACE, ...
                       'FaceAlpha', 0.18, 'EdgeColor', COL_PROBE_EDGE, 'LineWidth', 1.0);
    end
    if ~isempty(geom.angleTextPos)
        x1 = geom.h1El(1); z1 = geom.h1El(2);
        plot(ax, [x1, x1], [0.0, z1], 'Color', COL_WEDGE_EDGE, 'LineWidth', 0.9);
        text(ax, x1 + 0.8, z1 * 0.5, sprintf('h1=%.1f mm', abs(z1)), ...
             'FontSize', 7, 'Color', COL_WEDGE_EDGE);
        text(ax, geom.angleTextPos(1), geom.angleTextPos(2), ...
             sprintf('angle=%.1f deg', geom.wedgeAngDeg), 'FontSize', 7, ...
             'Color', COL_WEDGE_EDGE, 'HorizontalAlignment', 'center');
    end
end

function [legH, legL] = plotProjection(ax, dimCol, isXZ, elements, intPts, fp, ...
        activeIndices, isDualProbe, nHalf, wedgeAngDeg, thicknessMM, xLabelStr, titleStr)
    % Draws one X-Z or Y-Z projection: component fill/backwall, wedge +
    % probe overlay, interface line, element markers (active coloured /
    % inactive grey), envelope rays from the first & last ACTIVE element
    % of each array, and the focal point marker - with explicit padded
    % framing (mirrors python/scene.py draw_projection + finish_projection).
    %
    % elements, intPts, fp are in METRES (elements: Nx3, intPts: Nx3 with
    % zero-filled rows for inactive elements, fp: 1x3). dimCol selects
    % X (1) or Y (2) as the horizontal axis; column 3 is always Z depth.
    %
    % Returns legend handle/label arrays for the caller to pass to
    % legend() (only meaningful when this is the X-Z axes).
    COL_INACTIVE = [0.58 0.64 0.72];
    COL_MATERIAL = [0.58 0.64 0.72];
    COL_BACKWALL = [0.20 0.26 0.33];

    cla(ax); hold(ax, 'on');

    nEl = size(elements, 1);
    ec = elements(:, dimCol) * 1000;
    ez = elements(:, 3) * 1000;

    activeMask = false(nEl, 1);
    activeMask(activeIndices) = true;

    pairs = localActiveEnvelopePairs(activeIndices, isDualProbe, nHalf);

    % ---- Numeric bounds pass (nothing drawn yet, so the component
    % fill/backwall can be sized to the final frame and still rendered
    % behind everything else) ----
    boundsX = ec;
    boundsZ = ez;
    for r = 1:size(pairs, 1)
        for i = pairs(r, :)
            boundsX(end+1) = intPts(i, dimCol) * 1000; %#ok<AGROW>
            boundsZ(end+1) = intPts(i, 3) * 1000; %#ok<AGROW>
        end
    end
    boundsX(end+1) = fp(dimCol) * 1000;
    boundsZ(end+1) = fp(3) * 1000;

    wedgeGeom = localWedgeGeometry(ec, ez, isXZ, wedgeAngDeg);
    wedgeBoundsXZ = [wedgeGeom.wedgeVerts; wedgeGeom.probeVerts];
    if ~isempty(wedgeBoundsXZ)
        boundsX = [boundsX; wedgeBoundsXZ(:,1)];
        boundsZ = [boundsZ; wedgeBoundsXZ(:,2)];
    end

    if thicknessMM > 0
        boundsZ(end+1) = thicknessMM;
    end

    xmin = min(boundsX); xmax = max(boundsX);
    zmin = min(boundsZ); zmax = max(boundsZ);
    xpad = max(2.0, (xmax - xmin) * 0.08);
    zpad = max(2.0, (zmax - zmin) * 0.10);
    x0 = xmin - xpad; x1 = xmax + xpad;
    zTop = zmin - zpad; zBot = zmax + zpad;

    % ---- Draw back-to-front: component, wedge/probe, interface,
    % elements, rays, focal point ----
    fillBot = zBot;
    if thicknessMM > 0
        fillBot = thicknessMM;
    end
    hComponent = patch(ax, [x0, x1, x1, x0], [0, 0, fillBot, fillBot], COL_MATERIAL, ...
                       'FaceAlpha', 0.15, 'EdgeColor', 'none');

    hBackwall = [];
    if thicknessMM > 0
        hBackwall = yline(ax, thicknessMM, 'Color', COL_BACKWALL, 'LineWidth', 1.5);
    end

    [hWedge, hProbe] = localDrawWedge(ax, wedgeGeom);

    hInterface = yline(ax, 0, 'k-', 'LineWidth', 2);

    if isDualProbe
        halves = {1:nHalf, 'b'; (nHalf+1):nEl, 'r'};
    else
        halves = {1:nEl, 'r'};
    end
    hActive = [];
    hInactive = [];
    for hi = 1:size(halves, 1)
        sl = halves{hi, 1};
        colour = halves{hi, 2};
        m = activeMask(sl);
        cSl = ec(sl); zSl = ez(sl);
        if any(m)
            h = plot(ax, cSl(m), zSl(m), [colour 's'], 'MarkerSize', 4);
            if isempty(hActive); hActive = h; end
        end
        if any(~m)
            h = plot(ax, cSl(~m), zSl(~m), 's', 'Color', COL_INACTIVE, ...
                     'MarkerFaceColor', 'none', 'MarkerSize', 4);
            if isempty(hInactive); hInactive = h; end
        end
    end

    for r = 1:size(pairs, 1)
        i0 = pairs(r, 1);
        if isDualProbe && i0 > nHalf
            rc = 'r';
        else
            rc = 'b';
        end
        for i = pairs(r, :)
            pEl = [ec(i), ez(i)];
            pInt = [intPts(i, dimCol) * 1000, intPts(i, 3) * 1000];
            pFp = [fp(dimCol) * 1000, fp(3) * 1000];
            plot(ax, [pEl(1), pInt(1)], [pEl(2), pInt(2)], [rc '-']);
            plot(ax, [pInt(1), pFp(1)], [pInt(2), pFp(2)], [rc '-']);
        end
    end

    hFocal = plot(ax, fp(dimCol) * 1000, fp(3) * 1000, 'rx', 'MarkerSize', 8, 'LineWidth', 2);

    xlim(ax, [x0, x1]);
    ylim(ax, [zTop, zBot]);
    set(ax, 'YDir', 'reverse');
    daspect(ax, [1 1 1]);
    grid(ax, 'on');
    xlabel(ax, xLabelStr);
    ylabel(ax, 'Z Depth (mm)');
    title(ax, titleStr);
    hold(ax, 'off');

    legH = [];
    legL = {};
    if ~isempty(hActive);   legH(end+1) = hActive;   legL{end+1} = 'Elements';    end
    if ~isempty(hInactive); legH(end+1) = hInactive; legL{end+1} = 'Inactive';    end
    if ~isempty(hWedge);    legH(end+1) = hWedge;    legL{end+1} = 'Wedge';       end
    if ~isempty(hProbe);    legH(end+1) = hProbe;    legL{end+1} = 'Probe';       end
    legH(end+1) = hFocal;      legL{end+1} = 'Focal point';
    legH(end+1) = hInterface;  legL{end+1} = 'Interface';
    legH(end+1) = hComponent;  legL{end+1} = 'Component';
    if ~isempty(hBackwall)
        legH(end+1) = hBackwall; legL{end+1} = 'Backwall';
    end
end
