function tests = testFocalRules
%TESTFOCALRULES FocalRules against the shared Python case table, plus sign invariants.
tests = functiontests(localfunctions);
end

function testSharedCaseTable(test)
% tests/focal_rule_cases.json is written by python/make_focal_rule_cases.py from
% python/focal_rules.py; MATLAB must give the same targets and refusals (owner decision D1).
here = fileparts(mfilename('fullpath'));
data = jsondecode(fileread(fullfile(here, '..', 'tests', 'focal_rule_cases.json')));
cases = data.cases;
if ~iscell(cases), cases = num2cell(cases); end
verifyGreaterThan(test, numel(cases), 0);
for k = 1:numel(cases)
    c = cases{k};
    in = c.inputs;
    T = FocalRules.targets(caseSolver(in), in.mode, in.value, in.angles, in.skews, in.wave, ...
        in.y_mode, orEmpty(in.y_values));
    want = c.targets;
    if ~iscell(want), want = num2cell(want); end
    verifyEqual(test, numel(T), numel(want), c.name);
    for j = 1:min(numel(T), numel(want))
        w = want{j};
        label = sprintf('%s, target %d', c.name, j);
        verifyEqual(test, T(j).Angle, w.angle, 'AbsTol', 1e-12, label);
        verifyEqual(test, T(j).Skew, orNaN(w.skew), 'AbsTol', 1e-9, label);
        if isfield(w, 'reason')
            verifyEqual(test, T(j).Reason, w.reason, label);
        else
            verifyEqual(test, T(j).Reason, '', label);
            verifyEqual(test, [T(j).X, T(j).Y, T(j).Z], [w.x, w.y, w.z], 'AbsTol', 1e-12, label);
        end
    end
end
end

function testSkewSign(test)
% +skew turns the beam from +X towards +Y; the two foci mirror about the aperture centre.
s = DelayLaw(Probe(8, 1e-3, 5e6, 4, 1.2e-3), Wedge(30, 0.012, 2330, 0.003), Material(5920, 3240));
T = FocalRules.targets(s, 'constant-depth', 0.03, 45, [20, -20]);
c = s.apertureCentre();
verifyGreaterThan(test, T(1).Y, c(2));
verifyLessThan(test, T(2).Y, c(2));
verifyEqual(test, T(1).Y - c(2), c(2) - T(2).Y, 'AbsTol', 1e-12);
verifyEqual(test, T(1).X, T(2).X, 'AbsTol', 1e-12);
end

function testBadInputs(test)
s = DelayLaw(Probe(8, 1e-3), Wedge(30, 0.012, 2330), Material(5920));
verifyError(test, @() FocalRules.targets(s, 'banana', 0.03, 40), 'FocalRules:input');
verifyError(test, @() FocalRules.targets(s, 'constant-depth', 0.03, 40, 0, 'shear'), 'FocalRules:input');
verifyError(test, @() FocalRules.targets(s, 'sound-path', 0.03, 40, 0, 'longitudinal', 'fixed', 0), ...
    'FocalRules:input');
end

function s = caseSolver(in)
p = in.probe; w = in.wedge; m = in.material;
ny = field(p, 'ny', 1); pitchY = field(p, 'pitch_y', 0); order = field(p, 'order', 'column-first');
switch p.type
    case 'Linear'
        probe = Probe(p.n, p.pitch, 5e6, 1, 0, p.start, p.active, order);
    case 'Matrix'
        probe = Probe(p.n, p.pitch, 5e6, ny, pitchY, p.start, p.active, order);
    case 'Dual Linear'
        probe = DualProbe(p.n, p.pitch, 5e6, 1, 0, p.sep, p.start, p.active, order);
    case 'Dual Matrix'
        probe = DualProbe(p.n, p.pitch, 5e6, ny, pitchY, p.sep, p.start, p.active, order);
end
s = DelayLaw(probe, Wedge(w.angle, w.height, w.velocity, w.offset, w.roof), Material(m.vl, m.vs));
end

function v = field(s, name, default)
if isfield(s, name), v = s.(name); else, v = default; end
end

function v = orNaN(x)
if isempty(x), v = NaN; else, v = x; end
end

function v = orEmpty(x)
if isempty(x), v = []; else, v = x; end
end
