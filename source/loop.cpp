/*
loop.cpp
Loop object that will hold all information about the loop and be evolved in time.
*/

#include "loop.h"

Loop::Loop(char *ebtel_config, char *rad_config)
{
  tinyxml2::XMLDocument doc;
  tinyxml2::XMLElement *root;
  double helium_to_hydrogen_ratio;

  //Open file
  tinyxml2::XMLError load_ok = doc.LoadFile(ebtel_config);
  if(load_ok != 0)
  {
  	printf("Failed to load XML configuration file %s.\n",ebtel_config);
  	//TODO: Exit or break out from here
  }
  //Parse file and read into data structure
  root = doc.FirstChildElement();
  //Numeric parameters
  parameters.total_time = std::stod(get_element_text(root,"total_time"));
  parameters.tau = std::stod(get_element_text(root,"tau"));
  parameters.loop_length = std::stod(get_element_text(root,"loop_length"));
  parameters.rka_error = std::stod(get_element_text(root,"rka_error"));
  parameters.saturation_limit = std::stod(get_element_text(root,"saturation_limit"));
  parameters.c1_cond0 = std::stod(get_element_text(root,"c1_cond0"));
  parameters.c1_rad0 = std::stod(get_element_text(root,"c1_rad0"));
  helium_to_hydrogen_ratio = std::stod(get_element_text(root,"helium_to_hydrogen_ratio"));
  //Boolean parameters
  parameters.use_c1_loss_correction = string2bool(get_element_text(root,"use_c1_loss_correction"));
  parameters.use_c1_grav_correction = string2bool(get_element_text(root,"use_c1_grav_correction"));
  parameters.use_power_law_radiative_losses = string2bool(get_element_text(root,"use_power_law_radiative_losses"));
  parameters.use_spitzer_conductivity = string2bool(get_element_text(root,"use_spitzer_conductivity"));
  parameters.calculate_dem = string2bool(get_element_text(root,"calculate_dem"));
  //String parameters
  parameters.solver = get_element_text(root,"solver");
  parameters.output_filename = get_element_text(root,"output_filename");

  //Estimate results array length
  N = int(ceil(parameters.total_time/parameters.tau));

  //Initialize radiation model object
  if(parameters.use_power_law_radiative_losses)
  {
    radiation_model = new CRadiation();
  }
  else
  {
    radiation_model = new CRadiation(rad_config,false);
  }

  //Initialize heating object
  heater = new Heater(get_element(root,"heating"));

  //Initialize DEM object
  if(parameters.calculate_dem)
  {
    dem = new Dem(get_element(root,"dem"), radiation_model, N, parameters.loop_length, CalculateC2(), CalculateC3());
  }

  doc.Clear();

  // Calculate needed He abundance corrections
  CalculateAbundanceCorrection(helium_to_hydrogen_ratio);

  //Reserve memory for results
  results.time.resize(N);
  results.heat.resize(N);
  results.pressure_e.resize(N);
  results.pressure_i.resize(N);
  results.temperature_e.resize(N);
  results.temperature_i.resize(N);
  results.density.resize(N);
}

Loop::~Loop(void)
{
  //Destructor--free some stuff here
  delete heater;
  delete radiation_model;
  if(parameters.calculate_dem)
  {
    delete dem;
  }
}

void Loop::CalculateInitialConditions(void)
{
  int i = 0;
  int i_max = 100;
  double tol = 1e-2;
  double temperature_old = LARGEST_DOUBLE;
  double density_old = LARGEST_DOUBLE;
  double temperature,density;
  double radiative_loss;
  double error_temperature,error_density;
  double c1 = 2.0;
  double c2 = CalculateC2();
  double heat = heater->Get_Heating(0.0);

  while(i<i_max)
  {
    if(i > 0)
    {
      c1 = CalculateC1(temperature_old, temperature_old, density_old);
    }
    temperature = c2*pow(3.5*c1/(1.0 + c1)*pow(parameters.loop_length,2)*heat/(SPITZER_ELECTRON_CONDUCTIVITY + SPITZER_ION_CONDUCTIVITY),2.0/7.0);
    radiative_loss = radiation_model->GetPowerLawRad(log10(temperature));
    density = sqrt(heat/(radiative_loss*(1.0 + c1)));
    error_temperature = fabs(temperature - temperature_old)/temperature;
    error_density = fabs(density - density_old)/density;
    if(fmax(error_density,error_temperature) < tol)
    {
      break;
    }
    i++;
    temperature_old = temperature;
    density_old = density;
  }

  // Set current state in order pressure_e, pressure_i, density
  __state.resize(3);
  __state[0] = BOLTZMANN_CONSTANT*density*temperature;
  __state[1] = parameters.boltzmann_correction*BOLTZMANN_CONSTANT*density*temperature;
  __state[2] = density;

  //Save the results
  SaveResults(0,0.0);
}

void Loop::EvolveLoop(void)
{
  int i=1;
  double time = parameters.tau;
  double tau = parameters.tau;

  while(time<parameters.total_time)
  {
    // Solve Equations--update state
    if(parameters.solver.compare("euler")==0)
    {
      __state = EulerSolver(__state,time,tau);
    }
    else if(parameters.solver.compare("rk4")==0)
    {
      __state = RK4Solver(__state,time,tau);
    }
    else if(parameters.solver.compare("rka4")==0)
    {
      std::vector<double> _tmp_state;
      _tmp_state = RKA4Solver(__state,time,tau);
      tau = _tmp_state.back();
      _tmp_state.pop_back();
      __state = _tmp_state;
    }
    // Calculate DEM
    if(parameters.calculate_dem)
    {
      double tmp_temperature_e = __state[0]/(BOLTZMANN_CONSTANT*__state[2]);
      double tmp_temperature_i = __state[1]/(parameters.boltzmann_correction*BOLTZMANN_CONSTANT*__state[2]);
      // Calculate heat flux
      double tmp_fe = CalculateThermalConduction(tmp_temperature_e, __state[2], "electron");
      // Calculate C1
      double tmp_c1 = CalculateC1(tmp_temperature_e, tmp_temperature_i, __state[2]);
      dem->CalculateDEM(i, __state[0], __state[2], tmp_fe, tmp_c1);
    }
    // Save results
    SaveResults(i,time);
    //Update time and counter
    time += tau;
    i++;
  }

  //Set excess number of entries
  excess = N - i;
  if(excess<0)
  {
    excess = 0;
  }
}

void Loop::PrintToFile(void)
{
  int i;
  // Trim zeroes
  for(i=0;i<excess;i++)
  {
    results.time.pop_back();
    results.temperature_e.pop_back();
    results.temperature_i.pop_back();
    results.density.pop_back();
    results.pressure_e.pop_back();
    results.pressure_i.pop_back();
    results.heat.pop_back();
  }

  std::ofstream f;
  f.open(parameters.output_filename);
  for(i=0;i<results.time.size();i++)
  {
    f << results.time[i] << "\t" << results.temperature_e[i] << "\t" << results.temperature_i[i] << "\t" << results.density[i] << "\t" << results.pressure_e[i] << "\t" << results.pressure_i[i] << "\t" << results.heat[i] << "\n";
  }
  f.close();

  if(parameters.calculate_dem)
  {
    dem->PrintToFile(parameters.output_filename,excess);
  }
}

std::vector<double> Loop::CalculateDerivs(std::vector<double> state,double time)
{
  std::vector<double> derivs(3);
  double dpe_dt,dpi_dt,dn_dt;
  double psi_tr,psi_c,xi,R_c;

  double temperature_e = state[0]/(BOLTZMANN_CONSTANT*state[2]);
  double temperature_i = state[1]/(BOLTZMANN_CONSTANT*parameters.boltzmann_correction*state[2]);

  double f_e = CalculateThermalConduction(temperature_e,state[2],"electron");
  double f_i = CalculateThermalConduction(temperature_i,state[2],"ion");
  double radiative_loss = radiation_model->GetPowerLawRad(log10(temperature_e));
  double heat = heater->Get_Heating(time);
  double c1 = CalculateC1(temperature_e,temperature_i,state[2]);
  double c2 = CalculateC2();
  double c3 = CalculateC3();
  double collision_frequency = CalculateCollisionFrequency(temperature_e,state[2]);

  xi = state[0]/state[1];
  psi_c = parameters.loop_length/GAMMA_MINUS_ONE*collision_frequency*(state[1] - state[0]);
  R_c = pow(state[2],2)*radiative_loss*parameters.loop_length;
  psi_tr = (f_e + c1*R_c - xi*f_i)/(1.0 + xi);

  dpe_dt = GAMMA_MINUS_ONE/parameters.loop_length*(psi_tr + psi_c -R_c*(1.0 + c1)) + GAMMA_MINUS_ONE*heat*heater->partition;
  dpi_dt = -GAMMA_MINUS_ONE/parameters.loop_length*(psi_tr + psi_c) + GAMMA_MINUS_ONE*heat*(1.0 - heater->partition);
  dn_dt = c2*GAMMA_MINUS_ONE/(c3*parameters.loop_length*GAMMA*BOLTZMANN_CONSTANT*temperature_e)*(-f_e - c1*R_c + psi_tr);

  derivs[0] = dpe_dt;
  derivs[1] = dpi_dt;
  derivs[2] = dn_dt;

  return derivs;
}

void Loop::SaveResults(int i,double time)
{
  // calculate parameters
  double heat = heater->Get_Heating(time);
  double temperature_e = __state[0]/(BOLTZMANN_CONSTANT*__state[2]);
  double temperature_i = __state[1]/(BOLTZMANN_CONSTANT*parameters.boltzmann_correction*__state[2]);

  // Save results to results structure
  if(i >= N)
  {
    results.time.push_back(time);
    results.heat.push_back(heat);
    results.temperature_e.push_back(temperature_e);
    results.temperature_i.push_back(temperature_i);
    results.pressure_e.push_back(__state[0]);
    results.pressure_i.push_back(__state[1]);
    results.density.push_back(__state[2]);
  }
  else
  {
    results.time[i] = time;
    results.heat[i] = heat;
    results.temperature_e[i] = temperature_e;
    results.temperature_i[i] = temperature_i;
    results.pressure_e[i] = __state[0];
    results.pressure_i[i] = __state[1];
    results.density[i] = __state[2];
  }
}

double Loop::CalculateThermalConduction(double temperature, double density, std::string species)
{
  double kappa,mass,k_B;
  double f_c,f;
  double c2 = CalculateC2();

  if(species.compare("electron")==0)
  {
    kappa = SPITZER_ELECTRON_CONDUCTIVITY;
    mass = ELECTRON_MASS;
    k_B = BOLTZMANN_CONSTANT;
  }
  else
  {
    kappa = SPITZER_ION_CONDUCTIVITY;
    mass = parameters.ion_mass_correction*PROTON_MASS;
    k_B = parameters.boltzmann_correction*BOLTZMANN_CONSTANT;
  }

  f_c = -2.0/7.0*kappa*pow(temperature/c2,3.5)/parameters.loop_length;

  if(parameters.use_spitzer_conductivity)
  {
    f = f_c;
  }
  else
  {
    double f_s = -parameters.saturation_limit*1.5/sqrt(mass)*density*pow(k_B*temperature,1.5);
    f = -f_c*f_s/sqrt(pow(f_c,2) + pow(f_s,2));
  }

  return f;
}

double Loop::CalculateCollisionFrequency(double temperature_e, double density)
{
  // TODO: find a reference for this formula
  double coulomb_logarithm = 23.0 - log(sqrt(density/1.0e+13)*pow(BOLTZMANN_CONSTANT*temperature_e/(1.602e-9),-1.5));
  return 16.0*sqrt(_PI_)/3.0*ELECTRON_CHARGE_POWER_4/(parameters.ion_mass_correction*PROTON_MASS*ELECTRON_MASS)*pow(2.0*BOLTZMANN_CONSTANT*temperature_e/ELECTRON_MASS,-1.5)*density*coulomb_logarithm;
}

double Loop::CalculateC1(double temperature_e, double temperature_i, double density)
{
  double c1;
  double density_eqm_2,density_ratio;

  double c1_eqm0 = 2.0;
  double c2 = CalculateC2();
  double grav_correction = 1.0;
  double loss_correction = 1.0;
  double scale_height = CalculateScaleHeight(temperature_e,temperature_i);
  double radiative_loss = radiation_model->GetPowerLawRad(log10(temperature_e));

  if(parameters.use_c1_grav_correction)
  {
    grav_correction = exp(4.0*sin(_PI_/5.0)*parameters.loop_length/(_PI_*scale_height));
  }
  if(parameters.use_c1_loss_correction)
  {
    loss_correction = 1.95e-18*pow(temperature_e,-2.0/3.0)/radiative_loss;
  }

  density_eqm_2 = (SPITZER_ELECTRON_CONDUCTIVITY+SPITZER_ION_CONDUCTIVITY)*pow(temperature_e/c2,3.5)/(3.5*pow(parameters.loop_length,2)*c1_eqm0*loss_correction*grav_correction*radiative_loss);
  density_ratio = pow(density,2)/density_eqm_2;

  if(density_ratio<1.0)
  {
    c1 = (2.0*c1_eqm0 + parameters.c1_cond0*(1.0/density_ratio - 1.0))/(1.0 + 1.0/density_ratio);
  }
  else
  {
    c1 = (2.0*c1_eqm0 + parameters.c1_rad0*(density_ratio - 1.0))/(1.0 + density_ratio);
  }

  return c1*loss_correction*grav_correction;
}

double Loop::CalculateC2(void)
{
  return 0.9;
}

double Loop::CalculateC3(void)
{
  return 0.6;
}

double Loop::CalculateScaleHeight(double temperature_e,double temperature_i)
{
  return BOLTZMANN_CONSTANT*(temperature_e + parameters.boltzmann_correction*temperature_i)/(parameters.ion_mass_correction*PROTON_MASS)/SOLAR_SURFACE_GRAVITY;
}

void Loop::CalculateAbundanceCorrection(double helium_to_hydrogen_ratio)
{
  double z_avg = (1.0 + 2.0*helium_to_hydrogen_ratio)/(1.0 + helium_to_hydrogen_ratio);
  parameters.boltzmann_correction = (1.0 + 1.0/z_avg)/2.0;
  parameters.ion_mass_correction = (1.0 + 4.0*helium_to_hydrogen_ratio)/(2.0 + 3.0*helium_to_hydrogen_ratio)*2.0*parameters.boltzmann_correction;
}

std::vector<double> Loop::EulerSolver(std::vector<double> state,double time,double tau)
{
  std::vector<double> new_state(state.size());
  std::vector<double> derivs = CalculateDerivs(state, time);

  for(int i = 0;i<state.size();i++)
  {
    new_state[i] = state[i] + derivs[i]*tau;
  }

  return new_state;
}

std::vector<double> Loop::RK4Solver(std::vector<double> state, double time, double tau)
{
  int i;
  std::vector<double> new_state(state.size());
  std::vector<double> _tmp_state(state.size());

  std::vector<double> f1 = CalculateDerivs(state,time);
  for(i=0;i<f1.size();i++)
  {
    _tmp_state[i] = state[i] + tau/2.0*f1[i];
  }

  std::vector<double> f2 = CalculateDerivs(_tmp_state,time+tau/2.0);
  for(i=0;i<f2.size();i++)
  {
    _tmp_state[i] = state[i] + tau/2.0*f2[i];
  }

  std::vector<double> f3 = CalculateDerivs(_tmp_state,time+tau/2.0);
  for(i=0;i<f3.size();i++)
  {
    _tmp_state[i] = state[i] + tau*f3[i];
  }

  std::vector<double> f4 = CalculateDerivs(_tmp_state,time+tau);

  for(i=0;i<f4.size();i++)
  {
    new_state[i] = state[i] + tau/6.0*(f1[i] + 2.0*f2[i] + 2.0*f3[i] + f4[i]);
  }

  return new_state;
}

std::vector<double> Loop::RKA4Solver(std::vector<double> state, double time, double tau)
{
  std::vector<double> small_step;
  std::vector<double> big_step;
  std::vector<double> result;
  std::vector<double> _tmp_error_ratio(state.size());
  double scale,diff,old_tau;

  int i = 0;
  int max_try = 100;
  double error_ratio = LARGEST_DOUBLE;
  double safety_1 = 0.9;
  double safety_2 = 1.1;
  double safety_3 = 4.0;
  double epsilon = 1.0e-16;

  for(i=0;i < max_try;i++)
  {
    // Two small steps
    //small_step = RK4Solver(state,time,tau*0.5);
    small_step = RK4Solver(RK4Solver(state,time,tau*0.5),time+tau*0.5,tau*0.5);
    // Big step
    big_step = RK4Solver(state,time,tau);
    // Calculate error ratio
    for(int j=0;j<_tmp_error_ratio.size();j++)
    {
      scale = parameters.rka_error*(fabs(small_step[j]) + fabs(big_step[j]))/2.0;
      diff = small_step[j] - big_step[j];
      _tmp_error_ratio[j] = fabs(diff)/(scale+epsilon);
    }
    error_ratio = *std::max_element(_tmp_error_ratio.begin(),_tmp_error_ratio.end());
    // Estimate new value of tau
    old_tau = tau;
    tau = safety_1*old_tau*pow(error_ratio,-1.0/5.0);
    tau = fmax(tau,old_tau/safety_2);
    //DEBUG
    if(error_ratio<1)
    {
      tau = fmin(tau,safety_3*old_tau);
      small_step.push_back(tau);
      return small_step;
    }
  }

  if(i==max_try)
  {
    std::cout << "Warning! Adaptive solver did not converge to best step size." << std::endl;
  }

  // Update tau
  // tau = safety_1*old_tau*pow(error_ratio,-0.25);
  tau = fmin(tau,safety_3*old_tau);
  std::cout << "Returning a tau of " << tau << " at time " << time << std::endl;
  // Add the timestep to the returned state
  small_step.push_back(tau);

  return small_step;
}
