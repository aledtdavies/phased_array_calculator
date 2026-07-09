% Add the matlab folder to path
addpath('matlab');

% Setup test data
probe = Probe(64, 0.6e-3, 5e6, 1, 0, 0, 64, 'column-first');
wedge = Wedge(36.0, 15e-3, 2330.0);
material = Material(5920.0, 3240.0);
solver = DelayLaw(probe, wedge, material);

focal_points_x = linspace(-0.05, 0.05, 100);
focal_points_y = linspace(-0.05, 0.05, 10);
focal_z = 0.05;
wave_type = 'longitudinal';

% Warm up
solver.calculateLaw(0.0, 0.0, focal_z, wave_type);

tic;
count = 0;
for i = 1:length(focal_points_x)
    for j = 1:length(focal_points_y)
        x = focal_points_x(i);
        y = focal_points_y(j);
        solver.calculateLaw(x, y, focal_z, wave_type);
        count = count + 1;
    end
end
t = toc;
fprintf('Total time for %d calculations: %.4f seconds\n', count, t);
fprintf('Average time per calculation: %.6f seconds\n', t/count);
