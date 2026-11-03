'use strict';
overview=automationOverview;
render();
void dashboardLoad();
setInterval(()=>{if(state.page==='overview')void dashboardLoad();},15000);
