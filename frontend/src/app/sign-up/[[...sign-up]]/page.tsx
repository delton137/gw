import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="flex items-center justify-center py-24">
      <SignUp />
    </div>
  );
}
