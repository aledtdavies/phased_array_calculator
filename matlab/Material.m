% Material - Represents an ultrasonic material with defined velocities.
classdef Material
    properties
        VelocityLongitudinal % L-wave velocity in m/s
        VelocityShear        % S-wave velocity in m/s (optional)
    end
    
    methods
        function obj = Material(velocityLongitudinal, velocityShear)
            % Material Constructor
            obj.VelocityLongitudinal = velocityLongitudinal;
            
            if nargin > 1
                obj.VelocityShear = velocityShear;
            else
                obj.VelocityShear = [];
            end
        end
    end
end
