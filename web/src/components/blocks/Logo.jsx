import { LOGO_URL } from "../../utils";

export default function Logo() {
  return (
    <img
      src={LOGO_URL}
      alt="Capybara"
      className="w-12 h-12 rounded-full"
      onClick={() => (window.location.href = "/")}
    />
  );
}
