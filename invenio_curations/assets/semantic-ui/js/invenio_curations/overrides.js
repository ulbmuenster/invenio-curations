import { overrideStore } from "react-overridable";

import { DepositBox } from "./deposit/DepositBox";
import { curationComponentOverrides } from "./requests";

const overrides = {
  ...curationComponentOverrides,
  "InvenioAppRdm.Deposit.CardDepositStatusBox.container": DepositBox,
};
const registeredOverrides = overrideStore.getAll();

for (const [name, component] of Object.entries(overrides)) {
  if (!(name in registeredOverrides)) {
    overrideStore.add(name, component);
  }
}
