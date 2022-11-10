a = readtable('CD_Test_20221101__PDRamp.csv');
data = table2array(a);

%%
time = data(1:end,1);
torque = rescale(data(1:end,2));
fes = rescale(data(1:end,3));
window = rescale(data(1:end,4));

figure(); 
hold on; 
plot(time, torque)
plot(time, fes)
plot(time, window)

legend('Torque', 'FES', 'Window Flag')

%%
[a,b] = findpeaks(fes)
