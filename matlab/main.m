function main()
    % 1. Define Setup
    % Example: 5 MHz, 16 Elements, 0.6mm pitch
    probe = Probe(16, 0.6e-3, 5e6);
    
    % Material: Steel
    steel = Material(5900.0, 3240.0);
    
    % Wedge: Rexolite, 36 degree angle, 2330 m/s
    wedge = Wedge(36.0, 15e-3, 2330.0, 0.0);
    
    % 2. Initialize Solver
    solver = DelayLaw(probe, wedge, steel);
    
    % 3. Run Sector Scan
    depth = 50e-3;
    startAngle = 40;
    endAngle = 70;
    step = 1;
    
    scanData = generate_sector_scan(solver, depth, startAngle, endAngle, step);
    
    % 4. Export to MATLAB MAT file (native data structure)
    outputFileMat = 'focal_laws_matlab.mat';
    fprintf('Exporting to %s...\n', outputFileMat);
    save(outputFileMat, 'scanData');
    
    % Also export to CSV for compatibility
    outputFileCsv = 'focal_laws_matlab.csv';
    fprintf('Exporting to %s...\n', outputFileCsv);
    export_to_csv(outputFileCsv, scanData, probe.NumElements);
    
    fprintf('Done.\n');
end

function results = generate_sector_scan(solver, depth, startAngle, endAngle, step)
    angles = startAngle:step:endAngle;
    
    % Create empty struct array
    results = struct('Angle', [], 'FocalPoint', [], 'Delays', [], 'VelocityUsed', []);
    
    fprintf('Generating laws for %d angles...\n', length(angles));
    
    for i = 1:length(angles)
        angDeg = angles(i);
        angRad = deg2rad(angDeg);
        
        vWedge = solver.Wedge.Velocity;
        vMat = solver.Material.VelocityLongitudinal;
        
        % Snell's law to find interface crossing
        sinAlpha = (vWedge/vMat) * sin(angRad);
        if abs(sinAlpha) > 1.0
            fprintf('Angle %f Exceeds Critical Angle\n', angDeg);
            continue;
        end
        alphaRad = asin(sinAlpha);
        
        elements = solver.Wedge.getTransformedElements(solver.Probe);
        centerX = mean(elements(:, 1));
        centerZ = mean(elements(:, 2));
        
        hWedge = abs(centerZ);
        xInt = centerX + hWedge * tan(alphaRad);
        
        fz = depth;
        fx = xInt + fz * tan(angRad);
        
        law = solver.calculateLaw(fx, fz, 'longitudinal');
        
        results(i).Angle = angDeg;
        results(i).FocalPoint = [fx, fz];
        results(i).Delays = law.Delays;
        results(i).VelocityUsed = law.VelocityUsed;
    end
end

function export_to_csv(filename, scanData, numElements)
    fid = fopen(filename, 'w');
    
    % Headers
    headerList = {'LawID', 'Angle_Deg', 'Fx_mm', 'Fz_mm'};
    for i = 1:numElements
        headerList{end+1} = sprintf('El_%d_us', i);
    end
    
    fprintf(fid, '%s\n', strjoin(headerList, ','));
    
    % Write Data
    lawId = 1;
    for i = 1:length(scanData)
        law = scanData(i);
        if isempty(law.Angle)
            continue;
        end
        
        fprintf(fid, '%d,%.2f,%.4f,%.4f', lawId, law.Angle, ...
                law.FocalPoint(1) * 1000, law.FocalPoint(2) * 1000);
                
        delaysUs = law.Delays * 1e6;
        for j = 1:length(delaysUs)
            fprintf(fid, ',%.4f', delaysUs(j));
        end
        fprintf(fid, '\n');
        
        lawId = lawId + 1;
    end
    
    fclose(fid);
end
