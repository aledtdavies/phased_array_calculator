function tests=testDelayLaw
tests=functiontests(localfunctions);
end

function testAnalyticSnell(test)
s=DelayLaw(Probe(8,.0006),Wedge(20,.01,1480),Material(5900,3240));
alpha=deg2rad(12); beta=asin(5900/1480*sin(alpha));
direction=[.6,.8];
target=[(.01*tan(alpha)+.02*tan(beta))*direction,.02];
[x,y]=s.solveFermatPoint3D([0,0,-.01],target,1480,5900);
verifyEqual(test,[x,y],.01*tan(alpha)*direction,'AbsTol',1e-13);
end

function testGrazingRegression(test)
s=DelayLaw(Probe(8,.0006),Wedge(20,.01,1480),Material(5900,3240));
a=[0,0,-.002044892795101922]; b=[-.12862425783529333,0,.001223327348617447];
[x,y]=s.solveFermatPoint3D(a,b,1480,5900); q=[x,y,0];
residual=(q(1:2)-a(1:2))/(1480*norm(q-a))+(q(1:2)-b(1:2))/(5900*norm(q-b));
verifyLessThan(test,norm(residual),1e-12);
end

function testCentralRayStartsAtActiveApertureCentre(test)
p=Probe(16,.001,5e6,1,0,9,8);
s=DelayLaw(p,Wedge(20,.01,2330),Material(5900,3240));
elements=s.Wedge.getTransformedElements(p);
verifyEqual(test,s.apertureCentre(),mean(elements(9:16,:),1),'AbsTol',1e-15);
s=DelayLaw(Probe(16,.001),Wedge(20,.01,2330),Material(5900,3240));
verifyEqual(test,s.apertureCentre(),mean(elements,1),'AbsTol',1e-15);
end

function testLegacyTwoCoordinateCall(test)
s=DelayLaw(Probe(8,.0006),Wedge(20,.01,1480),Material(5900,3240));
a=s.calculateLaw(.03,.04); b=s.calculateLaw(.03,0,.04);
verifyEqual(test,a.FocalPoint,[.03,0,.04]);
verifyEqual(test,a.Delays,b.Delays);
verifyError(test,@()s.calculateLaw(.03,0,-.04),'DelayLaw:domain');
verifyError(test,@()s.calculateLaw(.03,0,.04,'banana'),'DelayLaw:mode');
end
