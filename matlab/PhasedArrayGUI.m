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
        elements = lastSolver.Wedge.getTransformedElements(lastSolver.Probe);
        
        isLinear = strcmp(currentProbeType, 'Linear');
        isDual = ismember(currentProbeType, {'Dual Linear', 'Dual Matrix'});
        
        % --- X-Z Plot ---
        cla(ax_xz); hold(ax_xz, 'on');
        yline(ax_xz, 0, 'k-', 'LineWidth', 2);
        
        if isDual
            nHalf = size(elements, 1) / 2;
            plot(ax_xz, elements(1:nHalf, 1)*1000, elements(1:nHalf, 3)*1000, 'bs', 'MarkerSize', 4);
            plot(ax_xz, elements(nHalf+1:end, 1)*1000, elements(nHalf+1:end, 3)*1000, 'rs', 'MarkerSize', 4);
        else
            plot(ax_xz, elements(:, 1)*1000, elements(:, 3)*1000, 'rs', 'MarkerSize', 4);
        end
        
        fp = res.FocalPoint;
        intPts = res.InterfacePoints;
        
        if isDual
            nHalf = size(elements, 1) / 2;
            
            % Array 1 (Tx) — Blue
            plot(ax_xz, [elements(1,1), intPts(1,1)]*1000, [elements(1,3), intPts(1,3)]*1000, 'b-');
            plot(ax_xz, [intPts(1,1), fp(1)]*1000, [intPts(1,3), fp(3)]*1000, 'b-');
            plot(ax_xz, [elements(nHalf,1), intPts(nHalf,1)]*1000, [elements(nHalf,3), intPts(nHalf,3)]*1000, 'b-');
            plot(ax_xz, [intPts(nHalf,1), fp(1)]*1000, [intPts(nHalf,3), fp(3)]*1000, 'b-');
            
            % Array 2 (Rx) — Red
            plot(ax_xz, [elements(nHalf+1,1), intPts(nHalf+1,1)]*1000, [elements(nHalf+1,3), intPts(nHalf+1,3)]*1000, 'r-');
            plot(ax_xz, [intPts(nHalf+1,1), fp(1)]*1000, [intPts(nHalf+1,3), fp(3)]*1000, 'r-');
            plot(ax_xz, [elements(end,1), intPts(end,1)]*1000, [elements(end,3), intPts(end,3)]*1000, 'r-');
            plot(ax_xz, [intPts(end,1), fp(1)]*1000, [intPts(end,3), fp(3)]*1000, 'r-');
        else
            % Single array — Blue
            plot(ax_xz, [elements(1,1), intPts(1,1)]*1000, [elements(1,3), intPts(1,3)]*1000, 'b-');
            plot(ax_xz, [intPts(1,1), fp(1)]*1000, [intPts(1,3), fp(3)]*1000, 'b-');
            plot(ax_xz, [elements(end,1), intPts(end,1)]*1000, [elements(end,3), intPts(end,3)]*1000, 'b-');
            plot(ax_xz, [intPts(end,1), fp(1)]*1000, [intPts(end,3), fp(3)]*1000, 'b-');
        end
        
        plot(ax_xz, fp(1)*1000, fp(3)*1000, 'rx', 'MarkerSize', 8, 'LineWidth', 2);
        
        xlabel(ax_xz, 'X (mm)'); ylabel(ax_xz, 'Z Depth (mm)');
        title(ax_xz, sprintf('X-Z  Angle: %.1f  Skew: %.1f', res.Angle, res.Skew));
        axis(ax_xz, 'equal'); set(ax_xz, 'YDir', 'reverse'); grid(ax_xz, 'on');
        hold(ax_xz, 'off');
        
        % --- Y-Z Plot ---
        if ~isLinear
            cla(ax_yz); hold(ax_yz, 'on');
            yline(ax_yz, 0, 'k-', 'LineWidth', 2);
            
            if isDual
                plot(ax_yz, elements(1:nHalf, 2)*1000, elements(1:nHalf, 3)*1000, 'bs', 'MarkerSize', 4);
                plot(ax_yz, elements(nHalf+1:end, 2)*1000, elements(nHalf+1:end, 3)*1000, 'rs', 'MarkerSize', 4);
            else
                plot(ax_yz, elements(:, 2)*1000, elements(:, 3)*1000, 'rs', 'MarkerSize', 4);
            end
            
            if isDual
                % Array 1 (Tx) — Blue
                plot(ax_yz, [elements(1,2), intPts(1,2)]*1000, [elements(1,3), intPts(1,3)]*1000, 'b-');
                plot(ax_yz, [intPts(1,2), fp(2)]*1000, [intPts(1,3), fp(3)]*1000, 'b-');
                plot(ax_yz, [elements(nHalf,2), intPts(nHalf,2)]*1000, [elements(nHalf,3), intPts(nHalf,3)]*1000, 'b-');
                plot(ax_yz, [intPts(nHalf,2), fp(2)]*1000, [intPts(nHalf,3), fp(3)]*1000, 'b-');
                
                % Array 2 (Rx) — Red
                plot(ax_yz, [elements(nHalf+1,2), intPts(nHalf+1,2)]*1000, [elements(nHalf+1,3), intPts(nHalf+1,3)]*1000, 'r-');
                plot(ax_yz, [intPts(nHalf+1,2), fp(2)]*1000, [intPts(nHalf+1,3), fp(3)]*1000, 'r-');
                plot(ax_yz, [elements(end,2), intPts(end,2)]*1000, [elements(end,3), intPts(end,3)]*1000, 'r-');
                plot(ax_yz, [intPts(end,2), fp(2)]*1000, [intPts(end,3), fp(3)]*1000, 'r-');
            else
                plot(ax_yz, [elements(1,2), intPts(1,2)]*1000, [elements(1,3), intPts(1,3)]*1000, 'b-');
                plot(ax_yz, [intPts(1,2), fp(2)]*1000, [intPts(1,3), fp(3)]*1000, 'b-');
                plot(ax_yz, [elements(end,2), intPts(end,2)]*1000, [elements(end,3), intPts(end,3)]*1000, 'b-');
                plot(ax_yz, [intPts(end,2), fp(2)]*1000, [intPts(end,3), fp(3)]*1000, 'b-');
            end
            
            plot(ax_yz, fp(2)*1000, fp(3)*1000, 'rx', 'MarkerSize', 8, 'LineWidth', 2);
            
            xlabel(ax_yz, 'Y (mm)'); ylabel(ax_yz, 'Z Depth (mm)');
            title(ax_yz, 'Y-Z Projection');
            axis(ax_yz, 'equal'); set(ax_yz, 'YDir', 'reverse'); grid(ax_yz, 'on');
            hold(ax_yz, 'off');
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
