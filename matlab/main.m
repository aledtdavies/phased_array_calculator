function main() % 1. Define Setup probe = Probe(16, 0.6e-3, 5e6);
steel = Material('Steel', 5900.0, 3240.0);
wedge = Wedge(36.0, 15e-3, 2330.0, -5e-3);

% 2. Initialize Solver solver = DelayLaw(probe, wedge, steel);

% 3. Run Sector Scan depth = 50e-3;
startAngle = 40;
endAngle = 70;
step = 1;

scanData = generate_sector_scan(solver, depth, startAngle, endAngle, step);

% 4. Export to CSV outputFile = 'focal_laws_matlab.csv';
fprintf('Exporting to %s...\n', outputFile);

fid = fopen(outputFile, 'w');

% Headers headerList = {'LawID', 'Angle_Deg', 'Fx_mm', 'Fz_mm'};
    for
      i = 1 : probe.NumElements headerList{end + 1} = sprintf('El_%d_us', i);
    end

        % Write header fprintf(fid, '%s', strjoin(headerList, ','));
    fprintf(fid, '\n');

    % Write Data
    for i = 1:length(scanData)
        law = scanData(i);

    % ID, Angle, Fx,
        Fz fprintf(fid, '%d,%.2f,%.4f,%.4f', i, law.Angle,
                   law.FocalPoint(1) * 1000, law.FocalPoint(2) * 1000);

    % Delays(in microseconds) delaysUs = law.Delays * 1e6;
    fprintf(fid, ',%.4f', delaysUs);
    fprintf(fid, '\n');
    end

        fclose(fid);
    fprintf('Done.\n');
    end

        function results =
            generate_sector_scan(solver, depth, startAngle, endAngle, step)
                angles = startAngle : step : endAngle;
    results = struct('Angle', {}, 'FocalPoint', {}, 'Delays', {});

    fprintf('Generating laws for %d angles...\n', length(angles));

    for
      i = 1 : length(angles) angDeg = angles(i);
    angRad = deg2rad(angDeg);

    fx = depth * sin(angRad);
    fz = depth * cos(angRad);

    law = solver.calculateLaw(fx, fz);

    results(i).Angle = angDeg;
    results(i).FocalPoint = [ fx, fz ];
    results(i).Delays = law.Delays;
    end end
