a = CD20220406163812(100:end, :);
figure(); 
c = linspecer(3);
hold on; 
plot(a(:,1), a(:,2), 'color', c(1,:));
scatter(a(:,1), a(:,2), 250, '.', 'MarkerFaceColor', c(1,:), 'MarkerEdgeColor', c(1,:))
plot(a(:,3), a(:,4), 'color', c(2,:)); 
plot(a(:,3), a(:,4), 'r.'); 
plot(a(:,1), a(:,6)+1, 'color', c(3,:))
legend('Thread Voltage', '', 'GUI Voltage', '', 'Window Flag')
ylim([1.246, 1.25])
